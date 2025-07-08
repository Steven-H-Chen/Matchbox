# matchbox/modes/classic_pvp.py

from fastapi import APIRouter, Header, HTTPException, Body
from pydantic import BaseModel
from uuid import uuid4
from typing import Dict, List, Optional
import random

router = APIRouter(prefix="/classic/pvp")

# --- in-memory store --------------------------------------------------------
# Each lobby: { mode, players, board, status, turn, score_x, score_o, rematch? }
LOBBIES: Dict[str, Dict] = {}

def new_board() -> List[str]:
    return [" "] * 9

def status(b: List[str]) -> str:
    wins = [
        (0,1,2),(3,4,5),(6,7,8),
        (0,3,6),(1,4,7),(2,5,8),
        (0,4,8),(2,4,6),
    ]
    for a,b1,c in wins:
        if b[a] != " " and b[a] == b[b1] == b[c]:
            return "x_wins" if b[a] == "x" else "o_wins"
    return "draw" if " " not in b else "in_progress"

def ident(auth: Optional[str], guest: Optional[str]) -> str:
    """
    Determine player ID from either Authorization header or X-Player-ID.
    """
    if auth:
        return auth
    if guest:
        return guest
    raise HTTPException(401, "no player id provided")

# --- request / response models ---------------------------------------------
class QueueReq(BaseModel):
    mode: str        # "classic"

class QueueResp(BaseModel):
    lobby_id: str
    waiting: bool
    side: str        # "x" or "o"

class PvPState(BaseModel):
    lobby_id: str
    board: List[str]
    status: str
    your_side: str
    turn: int
    score_x: int
    score_o: int

class MoveReq(BaseModel):
    lobby_id: str
    square: int

class RematchReq(BaseModel):
    lobby_id: str

class LeaveReq(BaseModel):
    lobby_id: str

# --- endpoints --------------------------------------------------------------
@router.post("/queue", response_model=QueueResp)
def queue(
    req: QueueReq = Body(...),
    x_player_id: str = Header(..., alias="X-Player-ID")
):
    # try to join an existing waiting lobby
    for lid, lob in LOBBIES.items():
        if lob["mode"] == req.mode and lob["status"] == "waiting":
            lob["players"].append(x_player_id)
            lob["status"] = "in_progress"
            return QueueResp(lobby_id=lid, waiting=False, side="o")

    # otherwise create a new one
    lid = str(uuid4())
    LOBBIES[lid] = {
        "mode":     req.mode,
        "players":  [x_player_id],
        "board":    new_board(),
        "status":   "waiting",
        "turn":     0,
        "score_x":  0,
        "score_o":  0,
        "rematch":  set(),
    }
    return QueueResp(lobby_id=lid, waiting=True, side="x")


@router.get("/state", response_model=PvPState)
def state(
    lobby_id: str,
    x_player_id: str = Header(..., alias="X-Player-ID")
):
    lob = LOBBIES.get(lobby_id)
    if not lob:
        raise HTTPException(404, "invalid lobby")
    if x_player_id not in lob["players"]:
        raise HTTPException(403, "not in lobby")

    your_idx = lob["players"].index(x_player_id)
    return PvPState(
        lobby_id  = lobby_id,
        board     = lob["board"],
        status    = lob["status"],
        your_side = "x" if your_idx == 0 else "o",
        turn      = lob["turn"],
        score_x   = lob["score_x"],
        score_o   = lob["score_o"],
    )


@router.post("/move", response_model=PvPState)
def move(
    req: MoveReq = Body(...),
    authorization: Optional[str] = Header(None),
    x_guest:      Optional[str] = Header(None, alias="X-Player-ID")
):
    pid = ident(authorization, x_guest)
    lob = LOBBIES.get(req.lobby_id)
    if not lob or lob["status"] != "in_progress":
        raise HTTPException(400, "no active match")
    if pid not in lob["players"]:
        raise HTTPException(403, "not in lobby")

    idx = lob["players"].index(pid)
    if idx != lob["turn"]:
        raise HTTPException(400, "not your turn")
    if lob["board"][req.square] != " ":
        raise HTTPException(400, "occupied")

    # place mark
    sym = "x" if idx == 0 else "o"
    lob["board"][req.square] = sym
    lob["status"] = status(lob["board"])

    # advance turn if still in progress
    if lob["status"] == "in_progress":
        lob["turn"] = 1 - idx
    return state(req.lobby_id, x_player_id=x_guest)


@router.post("/rematch")
def rematch(
    req: RematchReq = Body(...),
    authorization: Optional[str] = Header(None),
    x_guest:      Optional[str] = Header(None, alias="X-Player-ID")
):
    pid = ident(authorization, x_guest)
    lob = LOBBIES.get(req.lobby_id)
    if not lob or pid not in lob["players"]:
        raise HTTPException(404, "invalid lobby")

    lob["rematch"].add(pid)
    if len(lob["rematch"]) == 2:
        # both agreed → reset
        lob["board"]  = new_board()
        lob["turn"]   = 0
        random.shuffle(lob["players"])
        lob["status"] = "in_progress"
        lob["rematch"].clear()
    return {"status": lob["status"]}


@router.post("/leave")
def leave(
    req: LeaveReq = Body(...),
    authorization: Optional[str] = Header(None),
    x_guest:      Optional[str] = Header(None, alias="X-Player-ID")
):
    pid = ident(authorization, x_guest)
    lob = LOBBIES.get(req.lobby_id)
    if lob and pid in lob["players"]:
        LOBBIES.pop(req.lobby_id, None)
    return {"left": True}
