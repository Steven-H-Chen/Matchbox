# matchbox/main.py
import time
import json
import random
from uuid import uuid4
from typing import List, Dict, Optional

import redis
from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.staticfiles import StaticFiles

from matchbox.models import (
    NewReq, SoloMoveReq, QueueReq, GuessReq, PvPMoveReq, PvPState
)
from matchbox.lobby import Lobby
import matchbox.classic as classic
import matchbox.erase as erase_mod
import matchbox.experimental as exp_mod

# ── Redis Setup ──────────────────────────────────────────────────────────────
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
TIMEOUT = 15

def save_lobby(lob: Lobby):
    """Persist lobby JSON + expire it a bit after inactivity."""
    redis_client.set(f'lobby:{lob.id}', lob.to_json())
    redis_client.expire(f'lobby:{lob.id}', TIMEOUT * 10)

def load_lobby(lobby_id: str) -> Optional[Lobby]:
    """
    Load from Redis and reattach an erase-engine if needed.
    Returns None if not found.
    """
    data = redis_client.get(f'lobby:{lobby_id}')
    if not data:
        return None
    # supply factory for reattaching erase-mode logic
    return Lobby.from_json(
        data,
        erase_engine_factory=lambda: erase_mod.EraseEngine(json.loads(data)['board'])
    )

def delete_lobby(lobby_id: str):
    redis_client.delete(f'lobby:{lobby_id}')

# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI()
# serve your React/HTMX front-ends from `public/`
app.mount("/", StaticFiles(directory="public", html=True), name="static")

# In-memory solo games (no persistence)
SOLO_GAMES: Dict[str, dict] = {}

def ident(token: Optional[str], guest: Optional[str]) -> str:
    """Identify a player by Auth header or guest header or random UUID."""
    return token or guest or str(uuid4())

# ── Solo vs AI ────────────────────────────────────────────────────────────────
@app.post("/api/new")
def new_game(req: NewReq = Body(...)):
    # decide board size & AI engine
    size = 3 if req.mode in ("classic", "erase") else 5
    gid = str(uuid4())
    board = classic.new_board() if size == 3 else exp_mod.new_board_5()
    engine = erase_mod.EraseEngine(board) if req.mode == "erase" else None
    SOLO_GAMES[gid] = {
        "mode": req.mode,
        "board": board,
        "status": "in_progress",
        "erase": engine
    }
    return {"game_id": gid, "board": board, "status": "in_progress"}

@app.post("/api/move")
def solo_move(req: SoloMoveReq = Body(...)):
    g = SOLO_GAMES.get(req.game_id)
    if not g or g["status"] != "in_progress":
        raise HTTPException(400, "invalid game")
    board = g["board"]
    if board[req.square] != " ":
        raise HTTPException(400, "occupied")
    # player X
    board[req.square] = "x"
    if g["erase"]:
        g["erase"].record(req.square)
    st = classic.status(board)
    if st != "in_progress":
        g["status"] = st
        return {"game_id": req.game_id, "board": board, "status": st}
    # AI O
    ai_idx = classic.best_move(board)
    board[ai_idx] = "o"
    if g["erase"]:
        g["erase"].record(ai_idx)
    st = classic.status(board)
    g["status"] = st
    return {"game_id": req.game_id, "board": board, "status": st}

# ── PvP & Matchmaking ───────────────────────────────────────────────────────
@app.post("/api/queue")
def queue(
    req: QueueReq,
    authorization: Optional[str] = Header(None),
    x_guest: Optional[str] = Header(None, alias="X-Player-ID"),
):
    # trim stale
    now = time.time()
    for key in redis_client.scan_iter("lobby:*"):
        lid = key.split(":", 1)[1]
        lob = load_lobby(lid)
        if lob and lob.status == "waiting" and now - lob.created > TIMEOUT:
            delete_lobby(lob.id)

    pid = ident(authorization, x_guest)
    # look for a waiting same-mode lobby
    for key in redis_client.scan_iter("lobby:*"):
        lid = key.split(":", 1)[1]
        lob = load_lobby(lid)
        if lob and lob.mode == req.mode and lob.status == "waiting":
            lob.players.append(pid)
            lob.status = "matching"
            save_lobby(lob)
            return {"lobby_id": lob.id, "waiting": False}

    # create new
    board = classic.new_board() if req.mode in ("classic", "erase") else exp_mod.new_board_5()
    engine = erase_mod.EraseEngine(board) if req.mode == "erase" else None
    lob = Lobby(
        id=str(uuid4()),
        mode=req.mode,
        players=[pid],
        board=board,
        erase_engine=engine
    )
    save_lobby(lob)
    return {"lobby_id": lob.id, "waiting": True, "timeout": TIMEOUT}

@app.post("/api/guess")
def guess(req: GuessReq = Body(...)):
    lob = load_lobby(req.lobby_id)
    if not lob:
        raise HTTPException(400, "invalid lobby")
    guesses = getattr(lob, "guesses", {})
    guesses[req.player_id] = req.guess
    lob.__dict__["guesses"] = guesses
    save_lobby(lob)
    if len(guesses) < 2:
        return {"need": True}
    # tie?
    a, b = guesses.values()
    if a == b:
        lob.__dict__["guesses"] = {}
        save_lobby(lob)
        return {"tie": True}
    target = random.randint(1, 100)
    def score(p): return (abs(guesses[p] - target), -guesses[p])
    players_sorted = sorted(guesses.keys(), key=score)
    lob.players = players_sorted
    lob.status = "in_progress"
    save_lobby(lob)
    your_side = "x" if players_sorted[0] == req.player_id else "o"
    return {"your_side": your_side}

@app.get("/api/state", response_model=PvPState)
def state(
    lobby_id: str,
    authorization: Optional[str] = Header(None),
    x_guest: Optional[str] = Header(None, alias="X-Player-ID"),
):
    lob = load_lobby(lobby_id)
    if not lob:
        raise HTTPException(404)
    pid = ident(authorization, x_guest)
    if pid not in lob.players:
        raise HTTPException(403)
    side = "x" if lob.players[0] == pid else "o"
    opp = lob.players[1] if side == "x" else lob.players[0]
    return PvPState(
        lobby_id=lobby_id,
        board=lob.board,
        status=lob.status,
        your_side=side,
        turn=lob.turn,
        opponent=opp,
        score_x=lob.score_x,
        score_o=lob.score_o
    )

@app.post("/api/pvp/move", response_model=PvPState)
def pvp_move(
    req: PvPMoveReq = Body(...),
    authorization: Optional[str] = Header(None),
    x_guest: Optional[str] = Header(None, alias="X-Player-ID"),
):
    lob = load_lobby(req.lobby_id)
    pid = ident(authorization, x_guest)
    if not lob or lob.status != "in_progress":
        raise HTTPException(400)
    idx = lob.players.index(pid)
    if idx != lob.turn:
        raise HTTPException(400)
    if lob.board[req.square] != " ":
        raise HTTPException(400)
    sym = "x" if idx == 0 else "o"
    lob.board[req.square] = sym
    if lob.erase_engine:
        lob.erase_engine.record(req.square)
    if lob.mode == "experimental":
        exp_mod.check_points(lob)       # tally point for 3-in-a-row
        exp_mod.check_instant_win(lob)  # 5-in-a-row auto-win
    else:
        lob.status = classic.status(lob.board)

    if lob.status == "x_wins":
        lob.score_x += 1
    if lob.status == "o_wins":
        lob.score_o += 1
    if lob.status == "in_progress":
        lob.turn = 1 - idx

    save_lobby(lob)
    return state(req.lobby_id, authorization, x_guest)

@app.post("/api/rematch")
def rematch(
    lobby_id: str = Body(...),
    authorization: Optional[str] = Header(None),
    x_guest: Optional[str] = Header(None, alias="X-Player-ID"),
):
    lob = load_lobby(lobby_id)
    pid = ident(authorization, x_guest)
    if not lob or pid not in lob.players:
        raise HTTPException(404)
    lob.rematch.add(pid)
    if len(lob.rematch) == 2:
        # reset board & turn
        lob.board = classic.new_board() if lob.mode in ("classic", "erase") else exp_mod.new_board_5()
        lob.turn = 0
        lob.status = "in_progress"
        lob.rematch.clear()
    save_lobby(lob)
    return {"status": lob.status}

@app.post("/api/leave")
def leave(
    lobby_id: str = Body(...),
    authorization: Optional[str] = Header(None),
    x_guest: Optional[str] = Header(None, alias="X-Player-ID"),
):
    lob = load_lobby(lobby_id)
    if lob and ident(authorization, x_guest) in lob.players:
        delete_lobby(lobby_id)
    return {"left": True}
