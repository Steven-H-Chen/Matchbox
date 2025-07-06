# matchbox/classic.py
from typing import List, Optional

# Standard 3×3 Tic‑Tac‑Toe helpers
WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def new_board() -> List[str]:
    """Create a fresh 3x3 board (9 spaces)."""
    return [" "] * 9


def status(board: List[str]) -> str:
    """
    Evaluate board status:
     - 'x_wins' if X has won
     - 'o_wins' if O has won
     - 'draw' if full and no winner
     - 'in_progress' otherwise
    """
    # check wins
    for a, b, c in WIN_LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return 'x_wins' if board[a].lower() == 'x' else 'o_wins'
    # draw if no empty
    if all(cell != " " for cell in board):
        return 'draw'
    return 'in_progress'
