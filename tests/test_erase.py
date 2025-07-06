from matchbox.erase import EraseEngine

def test_purge_on_6th_move():
    board = [" "] * 9
    engine = EraseEngine(board)
    # simulate 6 placements at positions 0–5
    for i in range(6):
        engine.record(i)
    # after the 6th record, position 0 should be cleared
    assert board[0] == " "
    # the next oldest (1) stays until the 12th move
