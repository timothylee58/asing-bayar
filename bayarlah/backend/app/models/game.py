from pydantic import BaseModel, UUID4
from typing import Optional, Any
from datetime import datetime


class TanggaGenerateRequest(BaseModel):
    bill_id: UUID4
    participant_ids: list[UUID4]
    outcome_labels: list[str]


class TanggaLockRequest(BaseModel):
    bill_id: UUID4
    result: dict[str, str]  # participantId -> outcome


class RouletteSpinRequest(BaseModel):
    bill_id: UUID4
    participant_ids: list[UUID4]
    include_belanja_segment: bool = True


class RouletteLockRequest(BaseModel):
    bill_id: UUID4
    winner_participant_id: UUID4
    outcome: str


class GameResultResponse(BaseModel):
    id: UUID4
    bill_id: UUID4
    game_type: str
    seed: Optional[str]
    result_json: dict[str, Any]
    played_at: datetime
    is_locked: bool
