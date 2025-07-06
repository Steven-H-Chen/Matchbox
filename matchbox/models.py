from pydantic import BaseModel
from typing import List, Optional

# --- Request models ---
class NewReq(BaseModel):
    mode: str

class SoloMoveReq(BaseModel):
    game_id: str
    square: int

class QueueReq(BaseModel):
    mode: str

class GuessReq(BaseModel):
    lobby_id: str
    player_id: str
    guess: int

class PvPMoveReq(BaseModel):
    lobby_id: str
    square: int

# --- Response / state models ---
class PvPState(BaseModel):
    lobby_id: str
    board: List[str]
    status: str
    your_side: str
    turn: int
    opponent: Optional[str] = None
