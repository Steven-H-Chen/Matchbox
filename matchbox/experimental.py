from typing import List, Optional, Tuple

# all winning 5-length lines on 5×5
_WIN5 = []
# 5 rows
for r in range(5):
    _WIN5.append([r*5 + i for i in range(5)])
# 5 cols
for c in range(5):
    _WIN5.append([c + 5*i for i in range(5)])
# two diagonals
_WIN5.append([0, 6, 12, 18, 24])
_WIN5.append([4, 8, 12, 16, 20])

def check_instant_win(board: List[str]) -> Optional[str]:
    """
    If a player has 5 in a row anywhere, returns 'X' or 'O'. Otherwise None.
    """
    for line in _WIN5:
        vals = [board[i] for i in line]
        if vals == ['X']*5:
            return 'X'
        if vals == ['O']*5:
            return 'O'
    return None

def check_points(board: List[str]) -> Tuple[int,int]:
    """
    Count every 3-in-a-row segment for X and O (horizontal, vertical, diagonals).
    Returns (x_points, o_points).
    """
    x_score = o_score = 0

    # helper to scan any arbirary list of indices
    def scan_line(indices: List[int]):
        nonlocal x_score, o_score
        seq = [board[i] for i in indices]
        # slide a window of size 3 over this list
        for i in range(len(seq)-2):
            trip = seq[i:i+3]
            if trip == ['X']*3:
                x_score += 1
            elif trip == ['O']*3:
                o_score += 1

    # rows
    for r in range(5):
        scan_line([r*5 + i for i in range(5)])
    # cols
    for c in range(5):
        scan_line([c + 5*i for i in range(5)])
    # diag down-right
    scan_line([0,6,12,18,24])
    # diag down-left
    scan_line([4,8,12,16,20])

    return x_score, o_score
