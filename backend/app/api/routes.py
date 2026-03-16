from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.annotations.annotations import ProcessVideoRequest, ProcessedJobResponse
from app.core.database import get_db
from app.models.flight_path import FlightPath
from app.models.processed_job import ProcessedJob, PathPredictorType
from app.worker import process_drone_video

# Initialize the APIRouter for drone processing endpoints
router = APIRouter()


@router.post("/process")
async def process_video(
        request: ProcessVideoRequest,
        db: Session = Depends(get_db)
):
    """
    Endpoint to initiate drone video processing.

    This follows a 'Fire and Forget' pattern:
    1. Create database records for tracking.
    2. Offload the heavy ML processing to a Celery worker.
    3. Return an immediate success response to the user.
    """

    # --- 1. Create FlightPath Entry ---
    # Stores the metadata about the specific video file/link being analyzed
    flight_path = FlightPath(filename=request.gdrive_link)
    db.add(flight_path)
    db.commit()  # Flush to DB to generate an ID
    db.refresh(flight_path)

    # --- 2. Create ProcessedJob Entry ---
    # Tracks the lifecycle of the ML task (status: pending -> processing -> completed)
    job = ProcessedJob(
        flight_path_id=flight_path.id,
        video_url=request.gdrive_link,
        status="pending",
        path_predictor_type=request.path_predictor_type
    )
    db.add(job)
    db.commit()  # Job is now persistent and visible to the frontend

    # --- 3. Delegate to Celery Worker ---
    # .delay() pushes the task to Redis/RabbitMQ.
    # The FastAPI thread returns immediately, while the GPU worker picks this up in the background.
    process_drone_video.delay(
        flight_path.id,
        request.gdrive_link,
        request.start_lat,
        request.start_lon,
        request.path_predictor_type
    )

    # Return the Job ID so the frontend can start polling for updates via WebSockets/GET
    return {"id": job.id, "status": "pending"}


@router.get("/jobs")
def list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieves a paginated list of all processing jobs.
    Useful for the History or Dashboard view.
    """

    # 1. Count the total number of jobs (Required for frontend pagination math)
    total = db.query(func.count(ProcessedJob.id)).scalar()

    # 2. Fetch the paginated jobs, sorted by newest first
    jobs = (
        db.query(ProcessedJob)
        .order_by(ProcessedJob.processed_at.desc())
        .offset(skip)  # How many records to skip (page_number * limit)
        .limit(limit)  # Page size
        .all()
    )

    # 3. Return a structured response containing metadata and data
    return {"total": total, "items": jobs}


@router.get("/jobs/{job_id}", response_model=ProcessedJobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """
    Fetches detailed information for a single specific job.
    Includes the associated flight trajectory (GeoJSON).
    """

    # Use 'joinedload' to eagerly fetch the FlightPath object in a single SQL JOIN.
    # This prevents the 'N+1 problem' when accessing job.flight_path later.
    job = db.query(ProcessedJob).options(
        joinedload(ProcessedJob.flight_path)
    ).filter(ProcessedJob.id == job_id).first()

    # Standard 404 handling if the user provides an invalid ID
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job