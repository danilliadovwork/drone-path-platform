from app.core.database import get_db
from app.models.flight_path import FlightPath
from app.models.processed_job import ProcessedJob, PathPredictorType
from app.worker import process_drone_video
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.annotations.annotations import ProcessVideoRequest, ProcessedJobResponse

router = APIRouter()

@router.post("/process")
async def process_video(
        request: ProcessVideoRequest,
        db: Session = Depends(get_db)
):
    flight_path = FlightPath(filename=request.gdrive_link)
    db.add(flight_path)
    db.commit()
    db.refresh(flight_path)
    job = ProcessedJob(
        flight_path_id=flight_path.id,
        video_url=request.gdrive_link,
        status="pending",
        path_predictor_type=request.path_predictor_type
    )
    db.add(job)
    db.commit()
    process_drone_video.delay(
        flight_path.id,
        request.gdrive_link,
        request.start_lat,
        request.start_lon,
        request.path_predictor_type
    )

    return {"id": job.id, "status": "pending"}


@router.get("/jobs")
def list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # 1. Count the total number of jobs
    total = db.query(func.count(ProcessedJob.id)).scalar()

    # 2. Fetch the paginated jobs
    jobs = (
        db.query(ProcessedJob)
        .order_by(ProcessedJob.processed_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 3. Return both so the frontend can calculate pages
    return {"total": total, "items": jobs}

@router.get("/jobs/{job_id}", response_model=ProcessedJobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ProcessedJob).options(
        joinedload(ProcessedJob.flight_path)
    ).filter(ProcessedJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
