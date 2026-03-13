import datetime
import enum

from app.core.database import Base
from app.models.contants import DEFAULT_STRING_LENGTH
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship


class PathPredictorType(enum.Enum):
    DEEP_LEARNING = "DEEP_LEARNING"
    OPTICAL_FLOW = "OPTICAL_FLOW"

class ProcessedJob(Base):
    __tablename__ = "processed_jobs"

    id = Column(Integer, primary_key=True, index=True)
    flight_path_id = Column(Integer, ForeignKey("flight_paths.id"), nullable=True, unique=True)
    flight_path = relationship("FlightPath", back_populates="processed_job")
    processed_at = Column(DateTime, default=datetime.datetime.utcnow)
    video_url = Column(String(length=DEFAULT_STRING_LENGTH))
    status = Column(String(length=DEFAULT_STRING_LENGTH), default="completed")
    path_predictor_type = Column(String(length=DEFAULT_STRING_LENGTH), nullable=False)
