import pydantic


class NotificationData(pydantic.BaseModel):
    id: int
    status: str