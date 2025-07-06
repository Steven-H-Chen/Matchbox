import pytest
from matchbox.classic import new_board, status

def test_new_board_is_empty():
    b = new_board()
    assert b == [" "] * 9

@pytest.mark.parametrize("board,expected", [
    (["X","X","X"," "," "," "," "," "," "], "x_wins"),
    (["O","O","O"," "," "," "," "," "," "], "o_wins"),
    (["X","O","X","O","X","O","O","X","O"], "draw"),
    ([" "," "," "," "," "," "," "," "," "], "in_progress"),
])
def test_status(board, expected):
    assert status(board) == expected
