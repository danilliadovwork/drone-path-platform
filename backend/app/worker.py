import os
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.flight_path import FlightPath
from app.models.processed_job import ProcessedJob, PathPredictorType
from app.services.gdrive import GDriveService

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")


@celery_app.task(bind=True)
def process_drone_video(self, db_id: int, gdrive_link: str, start_lat: float, start_lon: float,
                        path_predictor_type: str):
    from app.path_predictors.optical_flow_path_prediction import OpticalFlowPathEstimator
    from app.path_predictors.deep_learning_path_prediction import DeepLearningPathEstimator
    from app.services.utils import extract_start_location
    import redis
    import json
    import datetime
    import logging

    db = SessionLocal()
    temp_file_path = None
    processed_job = None
    try:
        # 1. Fetch both the FlightPath and the existing ProcessedJob
        flight_path = db.query(FlightPath).filter(FlightPath.id == db_id).first()
        processed_job = db.query(ProcessedJob).filter(ProcessedJob.flight_path_id == db_id).first()

        if not flight_path or not processed_job:
            logging.error(f"FlightPath or ProcessedJob not found for ID: {db_id}")
            return

        # 2. Update status to 'processing' on the ProcessedJob
        processed_job.status = "processing"
        db.commit()

        r = redis.from_url(REDIS_URL)
        r.publish(f"job_updates_{db_id}", json.dumps({"status": "processing", "id": db_id}))
        logging.warning(f"📢 WORKER: Published 'processing' for job {db_id} to Redis")  # ADD THIS

        # Download video
        temp_file_path = GDriveService.download_file(gdrive_link)

        # Attempt to extract dynamic GPS coordinates from the video
        dynamic_coords = extract_start_location(temp_file_path)
        if dynamic_coords:
            logging.info(f"Extracted dynamic GPS: {dynamic_coords}")
            start_lat, start_lon = dynamic_coords
        else:
            logging.info("No embedded GPS found, falling back to user inputs.")

        # Process video with the determined coordinates
        logging.info(f"Path predictor type: {path_predictor_type}")
        if path_predictor_type == PathPredictorType.DEEP_LEARNING.value:
            estimator = DeepLearningPathEstimator(temp_file_path, start_lat, start_lon)
        else:
            estimator = OpticalFlowPathEstimator(temp_file_path, start_lat, start_lon)

        trajectory_geojson = estimator.process_video()

        # 3. Update trajectory and modify the existing ProcessedJob
        flight_path.trajectory = trajectory_geojson

        processed_job.status = "completed"
        processed_job.processed_at = datetime.datetime.utcnow()
        # video_url and path_predictor_type are already set in the router

        db.commit()

        # Publish success message to Redis
        r = redis.from_url(REDIS_URL)
        r.publish(f"job_updates_{db_id}", json.dumps({"status": "completed", "id": db_id}))

    except Exception as e:
        logging.error(f"Error processing video: {e}")

        # 4. Update the existing ProcessedJob status to 'failed'
        if processed_job:
            processed_job.status = "failed"
            db.commit()

        # Publish failure message
        r = redis.from_url(REDIS_URL)
        r.publish(f"job_updates_{db_id}", json.dumps({"status": "failed", "id": db_id, "error": str(e)}))

    finally:
        # Cleanup
        if temp_file_path:
            GDriveService.cleanup_file(temp_file_path)
        db.close()
