from pydantic import BaseModel


class PushTokenRegister(BaseModel):
    token: str
    participant_id: str


class PushMessage(BaseModel):
    to: str
    title: str
    body: str
    data: dict = {}
    sound: str = "default"
