from datetime import datetime
from typing import Annotated, Any, Optional

from pydantic import UUID4, BaseModel, Field, StringConstraints

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


class TanggaGenerateRequest(BaseModel):
    bill_id: UUID4
    participant_ids: list[UUID4] = Field(min_length=2, max_length=50)
    outcome_labels: list[Label] = Field(min_length=2, max_length=50)


class TanggaLockRequest(BaseModel):
    """Players pick lanes; the server derives every outcome from its own ladder.
    The client no longer reports results."""

    bill_id: UUID4
    lanes: dict[UUID4, int]  # participant id -> starting lane (0-based)


class RouletteSpinRequest(BaseModel):
    bill_id: UUID4
    participant_ids: list[UUID4] = Field(min_length=2, max_length=50)
    include_belanja_segment: bool = True  # accepted for client compatibility; unused


class RouletteLockRequest(BaseModel):
    """The winner is decided by the server at spin time. If the client reports
    one, it must match."""

    bill_id: UUID4
    winner_participant_id: Optional[UUID4] = None
    outcome: Optional[Label] = None


class DaduRollRequest(BaseModel):
    """The amount to split is the bill's own total, never a client value."""

    bill_id: UUID4
    participant_ids: list[UUID4] = Field(min_length=2, max_length=50)


class DaduLockRequest(BaseModel):
    bill_id: UUID4


class GameResultResponse(BaseModel):
    id: UUID4
    bill_id: UUID4
    game_type: str
    seed: Optional[str]
    result_json: dict[str, Any]
    played_at: datetime
    is_locked: bool
