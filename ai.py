WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]

def _winner(board: list[str]) -> str | None:
    for a, b, c in WIN_LINES:
        line = {board[a], board[b], board[c]}
        if line == {"X"}: return "X"
        if line == {"O"}: return "O"
    return None


def _score(board: list[str], depth: int) -> int | None:
    w = _winner(board)
    if w == "O": return 10 - depth
    if w == "X": return depth - 10
    if " " not in board: return 0
    return None


def best_move(board: list[str]) -> int:
    def minimax(b, depth, is_ai, alpha, beta):
        sc = _score(b, depth)
        if sc is not None: return sc, -1
        best_val, best_sq = (-(10**6), -1) if is_ai else (10**6, -1)
        for i, v in enumerate(b):
            if v != " ": continue
            b[i] = "O" if is_ai else "X"
            val, _ = minimax(b, depth+1, not is_ai, alpha, beta)
            b[i] = " "
            if is_ai:
                if val > best_val:
                    best_val, best_sq = val, i
                    alpha = max(alpha, val)
            else:
                if val < best_val:
                    best_val, best_sq = val, i
                    beta = min(beta, val)
            if beta <= alpha: break
        return best_val, best_sq
    _, move = minimax(board, 0, True, -10**6, 10**6)
    return move