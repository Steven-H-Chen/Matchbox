# matchbox/modes/classic_pvp.py

import os
import time
import json
from uuid import uuid4
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Header, Body

# Firebase Admin SDK
from firebase_admin import credentials, initialize_app, db

# your Pydantic request/response models
from matchbox.models import QueueReq, PvPState, PvPMoveReq

router = APIRouter(prefix="/classic/pvp")

# ── Config ────────────────────────────────────────────────
TIMEOUT       = 15
RTDB_ROOT     = None  # will be set after init


# ── Board helpers ─────────────────────────────────────────
def new_board() -> List[str]:
    """Return a blank 3×3 board."""
    return [" "] * 9

def status(b: List[str]) -> str:
    """Compute game status: 'x_wins', 'o_wins', 'draw', or 'in_progress'."""
    wins = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6),
    ]
    for a, c, d in wins:
        if b[a] != " " and b[a] == b[c] == b[d]:
            return "x_wins" if b[a] == "x" else "o_wins"
    return "draw" if " " not in b else "in_progress"


# ── Firebase RTDB setup ────────────────────────────────────
raw_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if not raw_json:
    raise RuntimeError("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON env-var")
sa_data = json.loads(raw_json)

cred = credentials.Certificate(sa_data)
initialize_app(cred, {
    "databaseURL": os.environ.get("FIREBASE_DB_URL")
})
RTDB_ROOT = db.reference()


# ── Auth helper ────────────────────────────────────────────
def ident(authorization: Optional[str], x_player: Optional[str]):
    """
    We expect the frontend has already verified the Firebase ID token
    and set X-Player-ID = firebaseUser.uid.
    """
    if not x_player:
        raise HTTPException(401, "Missing X-Player-ID header")
    return x_player


# ── Queue endpoint ────────────────────────────────────────
@router.post("/queue")
def queue(
    req: QueueReq,
    authorization: Optional[str]  = Header(None),
    x_player_id: Optional[str]    = Header(None, alias="X-Player-ID"),
):
    me  = ident(authorization, x_player_id)
    now = int(time.time())

    # prune stale entries
    qref = RTDB_ROOT.child("queues").child("classic")
    for uid, entry in (qref.get() or {}).items():
        if now - entry.get("joinedAt", 0) > TIMEOUT:
            qref.child(uid).delete()

    # try to match
    for uid in (qref.get() or {}):
        if uid != me:
            # found opponent → create match
            lobby_id  = str(uuid4())
            board     = new_board()
            match_ref = RTDB_ROOT.child("matches/classic").child(lobby_id)
            match_ref.set({
                "board":   board,
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

    # still no match → enqueue self
    qref.child(me).set({"joinedAt": now})
    return {"lobby_id": None, "waiting": True, "timeout": TIMEOUT}


# ── State endpoint ────────────────────────────────────────
@router.get("/state", response_model=PvPState)
def state(
    lobby_id: str,
    authorization: Optional[str]  = Header(None),
    x_player_id: Optional[str]    = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches/classic").child(lobby_id)
    data      = match_ref.get()
    if not data:
        raise HTTPException(404, "Lobby not found")
    if me not in data["players"].values():
        raise HTTPException(403, "Not a participant")

    your_side = data["turn"]
    turn_idx  = 0 if your_side == "x" else 1
    opponent  = data["players"]["o" if your_side == "x" else "x"]

    return PvPState(
        lobby_id = lobby_id,
        board    = data["board"],
        status   = data["status"],
        your_side= your_side,
        turn     = turn_idx,
        opponent = opponent,
        score_x  = data.get("score_x", 0),
        score_o  = data.get("score_o", 0),
    )


# ── Move endpoint ────────────────────────────────────────
@router.post("/move", response_model=PvPState)
def pvp_move(
    req: PvPMoveReq             = Body(...),
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str]   = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches/classic").child(req.lobby_id)
    data      = match_ref.get()
    if not data or data["status"] != "in_progress":
        raise HTTPException(400, "Invalid lobby or game over")

    # whose turn?
    sym = data["turn"]
    if data["players"][sym] != me:
        raise HTTPException(400, "Not your turn")
    if data["board"][req.square] != " ":
        raise HTTPException(400, "Square taken")

    # apply move
    data["board"][req.square] = sym
    st                        = status(data["board"])
    data["status"]            = st

    if st == "in_progress":
        data["turn"] = "o" if sym == "x" else "x"
    else:
        if st == "x_wins":
            data["score_x"] = data.get("score_x", 0) + 1
        if st == "o_wins":
            data["score_o"] = data.get("score_o", 0) + 1

    match_ref.set(data)
    return state(req.lobby_id, authorization, x_player_id)


# ── Rematch endpoint ─────────────────────────────────────
@router.post("/rematch")
def rematch(
    lobby_id: str               = Body(...),
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str]   = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches/classic").child(lobby_id)
    data      = match_ref.get()
    if not data or me not in data["players"].values():
        raise HTTPException(404, "Invalid lobby")

    # reset board & turn, keep scores
    data.update({
        "board":  new_board(),
        "turn":   "x",
        "status": "in_progress"
    })
    match_ref.set(data)
    return {"status": "in_progress"}


# ── Leave endpoint ───────────────────────────────────────
@router.post("/leave")
def leave(
    lobby_id: str               = Body(...),
    authorization: Optional[str] = Header(None),
    x_player_id: Optional[str]   = Header(None, alias="X-Player-ID"),
):
    me        = ident(authorization, x_player_id)
    match_ref = RTDB_ROOT.child("matches/classic").child(lobby_id)
    data      = match_ref.get()
    if data and me in data["players"].values():
        match_ref.delete()
    return {"left": True}
