# matchbox/modes/classic_pvp.py

import os
import time
import json
from uuid import uuid4
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Body

# Firebase Admin SDK
from firebase_admin import credentials, initialize_app, db

# your Pydantic request/response models
from matchbox.models import QueueReq, PvPState, PvPMoveReq

# ── local Tic-Tac-Toe logic (no external classic module) ──

def new_board() -> List[str]:
    """Return a blank 3×3 board."""
    return [" "] * 9

def status(b: List[str]) -> str:
    """Compute game status: 'x_wins', 'o_wins', 'draw', or 'in_progress'."""
    wins = [
        (0,1,2),(3,4,5),(6,7,8),
        (0,3,6),(1,4,7),(2,5,8),
        (0,4,8),(2,4,6),
    ]
    for a,c,d in wins:
        if b[a] != " " and b[a] == b[c] == b[d]:
            return "x_wins" if b[a] == "x" else "o_wins"
    return "draw" if " " not in b else "in_progress"

# ── Firebase RTDB setup ────────────────────────────────────
sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if not sa_path or not os.path.exists(sa_path):
    raise RuntimeError("Missing or invalid GOOGLE_APPLICATION_CREDENTIALS")

cred = credentials.Certificate(sa_path)
initialize_app(cred, {
    "databaseURL": os.environ.get("FIREBASE_DB_URL")
})

router = APIRouter(prefix="/classic/pvp")
TIMEOUT   = 15
RTDB_ROOT = db.reference()

def ident(authorization: Optional[str], x_player: Optional[str]):
    """
    We expect the frontend to set X-Player-ID = firebaseUser.uid.
    """
    if not x_player:
        raise HTTPException(401, "Missing X-Player-ID header")
    return x_player

@router.post("/queue")
def queue(
    req: QueueReq,
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str] = Header(None, alias="X-Player-ID"),
):
    me  = ident(authorization, x_player_id)
    now = int(time.time())

    # prune stale queue entries
    qref = RTDB_ROOT.child("queues").child("classic")
    for uid, entry in (qref.get() or {}).items():
        if now - entry.get("joinedAt", 0) > TIMEOUT:
            qref.child(uid).delete()

    # try to match with someone else
    for uid in (qref.get() or {}):
        if uid != me:
            lobby_id = str(uuid4())
            match_ref = RTDB_ROOT.child("matches").child("classic").child(lobby_id)
            match_ref.set({
                "board":   new_board(),
                "players": {"x": me, "o": uid},
                "turn":    "x",
                "status":  "in_progress",
                "score_x": 0,
                "score_o": 0
            })
            # remove both from queue
            qref.child(uid).delete()
            qref.child(me).delete()
            return {"lobby_id": lobby_id, "waiting": False}

    # no opponent yet, enqueue self
    qref.child(me).set({"joinedAt": now})
    return {"lobby_id": None, "waiting": True, "timeout": TIMEOUT}

@router.get("/state", response_model=PvPState)
def state(
    lobby_id: str,
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str] = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches").child("classic").child(lobby_id)
    data      = match_ref.get()
    if not data:
        raise HTTPException(404, "Lobby not found")
    if me not in data["players"].values():
        raise HTTPException(403, "Not a participant")

    your_side = data["turn"]
    turn_idx  = 0 if your_side == "x" else 1
    opponent  = data["players"]["o" if your_side == "x" else "x"]

    return PvPState(
        lobby_id=lobby_id,
        board=data["board"],
        status=data["status"],
        your_side=your_side,
        turn=turn_idx,
        opponent=opponent,
        score_x=data.get("score_x", 0),
        score_o=data.get("score_o", 0),
    )

@router.post("/move", response_model=PvPState)
def pvp_move(
    req: PvPMoveReq = Body(...),
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str] = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches").child("classic").child(req.lobby_id)
    data      = match_ref.get()
    if not data or data["status"] != "in_progress":
        raise HTTPException(400, "Invalid lobby or game over")

    expected = data["turn"]
    sym      = expected
    if data["players"][sym] != me:
        raise HTTPException(400, "Not your turn")
    if data["board"][req.square] != " ":
        raise HTTPException(400, "Square taken")

    # make move
    data["board"][req.square] = sym
    st = status(data["board"])
    data["status"] = st

    if st == "in_progress":
        data["turn"] = "o" if sym == "x" else "x"
    else:
        if st == "x_wins":
            data["score_x"] = data.get("score_x", 0) + 1
        if st == "o_wins":
            data["score_o"] = data.get("score_o", 0) + 1

    match_ref.set(data)
    return state(req.lobby_id, authorization, x_player_id)

@router.post("/rematch")
def rematch(
    lobby_id: str = Body(...),
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str] = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches").child("classic").child(lobby_id)
    data      = match_ref.get()
    if not data or me not in data["players"].values():
        raise HTTPException(404, "Invalid lobby")

    # reset board, keep scores
    data["board"]  = new_board()
    data["turn"]   = "x"
    data["status"] = "in_progress"
    match_ref.set(data)
    return {"status": "in_progress"}

@router.post("/leave")
def leave(
    lobby_id: str = Body(...),
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str] = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches").child("classic").child(lobby_id)
    data      = match_ref.get()
    if data and me in data["players"].values():
        match_ref.delete()
    return {"left": True}
