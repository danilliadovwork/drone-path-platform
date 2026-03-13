import json
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime
from geoalchemy2.elements import WKBElement
from geoalchemy2.shape import to_shape
import shapely.geometry


class ProcessVideoRequest(BaseModel):
    gdrive_link: str
    start_lat: float
    start_lon: float
    path_predictor_type: str


class FlightPathResponse(BaseModel):
    id: int
    filename: Optional[str] = None
    trajectory: Optional[str] = None

    @field_validator('trajectory', mode='before')
    @classmethod
    def parse_geometry(cls, v):
        if isinstance(v, WKBElement):
            shape = to_shape(v)
            return json.dumps(shapely.geometry.mapping(shape))
        return v

    model_config = ConfigDict(from_attributes=True)


class ProcessedJobResponse(BaseModel):
    id: int
    flight_path_id: Optional[int]
    processed_at: Optional[datetime]
    video_url: Optional[str]
    status: Optional[str]
    path_predictor_type: str
    flight_path: Optional[FlightPathResponse] = None
    model_config = ConfigDict(from_attributes=True)
