from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from app.core.database import Base

from app.models.contants import SMALL_STRING_LENGTH


class FlightPath(Base):
    __tablename__ = "flight_paths"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(length=SMALL_STRING_LENGTH), index=True)
    trajectory = Column(Geometry(geometry_type='LINESTRING', srid=4326))
    
    processed_job = relationship("ProcessedJob", back_populates="flight_path", uselist=False)