from collections import deque
from typing import Optional

class EraseEngine:
    """
    Tracks move history and purges the oldest entry every N moves.
    After 18 total moves, the window shrinks to N-1; after 28, to N-2 (min 4).
    """
    def __init__(self, window: int = 6):
        self.window = window
        self.history = deque()
        self.total_moves = 0
        self.current_window = window

    def record(self, square: int) -> Optional[int]:
        """
        Add a move index. If history exceeds current window size, purge and return the oldest index.
        Otherwise return None.
        """
        self.total_moves += 1
        # adjust dynamic window after thresholds
        if self.total_moves > 28:
            self.current_window = max(self.window - 2, 4)
        elif self.total_moves > 18:
            self.current_window = max(self.window - 1, 5)
        # append new move
        self.history.append(square)
        # purge if over window
        if len(self.history) > self.current_window:
            return self.history.popleft()
        return None
