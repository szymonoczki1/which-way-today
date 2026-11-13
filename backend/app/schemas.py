from datetime import time

from pydantic import BaseModel, ConfigDict, Field


class TripBase(BaseModel):
    # Trip (SQLModel) instances are returned directly as response_model=TripRead;
    # from_attributes lets pydantic read them by attribute instead of requiring a dict.
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=100)
    origin_address: str = Field(min_length=1)
    origin_lat: float = Field(ge=-90, le=90)
    origin_lon: float = Field(ge=-180, le=180)
    destination_address: str = Field(min_length=1)
    destination_lat: float = Field(ge=-90, le=90)
    destination_lon: float = Field(ge=-180, le=180)
    usual_departure_time: time | None = None


class TripCreate(TripBase):
    pass


class TripUpdate(TripBase):
    pass


class TripRead(TripBase):
    id: int
