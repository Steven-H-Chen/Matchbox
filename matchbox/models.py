# matchbox/models.py

from pydantic import BaseModel
from typing import List

class QueueReq(BaseModel):
    mode: str

class PvPMoveReq(BaseModel):
    lobby_id: str
    square: int

class PvPState(BaseModel):
    lobby_id: str
    board: List[str]
    status: str
    your_side: str
    turn: int
    opponent: str
    score_x: int
    score_o: int
