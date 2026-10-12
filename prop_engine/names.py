"""Player-name keys for joining books that spell names differently."""

from __future__ import annotations

import re
import unicodedata

_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def player_key(name: str) -> str:
    """'Marvin Harrison Jr.' and 'marvin harrison' -> 'marvin harrison'."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower().replace("'", "").replace(".", ""))
    parts = [p for p in text.split() if p]
    while len(parts) > 2 and parts[-1] in _SUFFIXES:
        parts.pop()
    return " ".join(parts)
