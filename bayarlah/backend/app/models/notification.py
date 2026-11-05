from typing import Annotated

from pydantic import BaseModel, StringConstraints


class PushTokenRegister(BaseModel):
    """Organiser device token. Identity comes from the auth token, never the body."""

    token: Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=200)]
