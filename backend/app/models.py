from datetime import time

from sqlmodel import Field, SQLModel


class Trip(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    origin_address: str
    origin_lat: float
    origin_lon: float
    destination_address: str
    destination_lat: float
    destination_lon: float
    usual_departure_time: time | None = None
