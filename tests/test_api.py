import pytest
from fastapi.testclient import TestClient
from matchbox.main import app

client = TestClient(app)

def test_queue_and_match_classic():
    # enqueue two players and verify the second is matched
    r1 = client.post("/api/queue", json={"mode":"classic"})
    r2 = client.post("/api/queue", json={"mode":"classic"})
    assert r1.status_code == 200
    assert r2.json().get("waiting") is False

def test_solo_game_flow():
    # new game, make a move, get updated board
    new = client.post("/api/new", json={"mode":"classic"}).json()
    gid = new["game_id"]
    mv = client.post("/api/move", json={"game_id": gid, "square": 0})
    assert mv.status_code == 200
    data = mv.json()
    assert "board" in data and data["board"][0] == "x"
