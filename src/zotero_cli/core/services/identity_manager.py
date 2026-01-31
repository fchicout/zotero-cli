import random
from typing import List


class IdentityManager:
    """
    Manages user identities (User-Agents) to avoid fingerprinting and blocks.
    """

    # Common User-Agents
    USER_AGENTS: List[str] = [
        # Chrome / Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox / Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari / macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Chrome / macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Edge / Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    def __init__(self):
        self._current_index = 0
        # Shuffle initially to ensure randomness across runs
        random.shuffle(self.USER_AGENTS)

    def get_current_identity(self) -> str:
        """Returns the current User-Agent string."""
        return self.USER_AGENTS[self._current_index]

    def rotate_identity(self) -> str:
        """
        Rotates to the next identity in the pool and returns it.
        Useful when a soft-block (403) is encountered.
        """
        self._current_index = (self._current_index + 1) % len(self.USER_AGENTS)
        return self.get_current_identity()

    def get_random_identity(self) -> str:
        """Returns a random User-Agent from the pool without changing state."""
        return random.choice(self.USER_AGENTS)
