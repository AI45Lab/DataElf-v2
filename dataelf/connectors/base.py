from __future__ import annotations

from typing import Protocol


class Connector(Protocol):
    name: str
