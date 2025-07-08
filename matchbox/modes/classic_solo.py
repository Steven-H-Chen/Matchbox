# matchbox/modes/classic_solo.py
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from uuid import uuid4
from typing import Dict, List

from ai import best_move           # ← your existing Minimax helper

router = APIRouter()

# --- in-memory store (keep it simple for now) --------------------
GAMES: Dict[str, Dict] = {}        # {game_id: {"board": [...], "status": str}}

def new_board() -> List[str]:
    return [" "] * 9               # 3×3 flattened

def status(b: List[str]) -> str:
    wins = [(0,1,2),(3,4,5),(6,7,8),
            (0,3,6),(1,4,7),(2,5,8),
            (0,4,8),(2,4,6)]
    for a,b1,c in wins:
        if b[a] != " " and b[a] == b[b1] == b[c]:
            return "x_wins" if b[a] == "x" else "o_wins"
    return "draw" if " " not in b else "in_progress"

# --- request / response models ----------------------------------
class NewGameResp(BaseModel):
    game_id: str
    board: List[str]
    status: str

class MoveReq(BaseModel):
    game_id: str
    square: int        # 0-8

class MoveResp(NewGameResp):  ...

# --- endpoints --------------------------------------------------
@router.post("/new", response_model=NewGameResp)
def new_game():
    gid = str(uuid4())
    GAMES[gid] = {"board": new_board(), "status": "in_progress"}
    return {"game_id": gid, "board": GAMES[gid]["board"], "status": "in_progress"}

@router.post("/move", response_model=MoveResp)
def move(req: MoveReq = Body(...)):
    g = GAMES.get(req.game_id)
    if not g or g["status"] != "in_progress":
        raise HTTPException(400, "invalid game")
    board = g["board"]

    if board[req.square] != " ":
        raise HTTPException(400, "occupied")

    # Player (X)
    board[req.square] = "x"
    g["status"] = status(board)
    if g["status"] != "in_progress":
        return {"game_id": req.game_id, "board": board, "status": g["status"]}

    # AI (O)
    ai_idx = best_move(board)
    board[ai_idx] = "o"
    g["status"] = status(board)
    return {"game_id": req.game_id, "board": board, "status": g["status"]}
