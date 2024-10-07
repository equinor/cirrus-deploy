from __future__ import annotations
from abc import ABC


class Derivation(ABC):
    def src(self) -> Derivation:
        pass

    def __fspath__(self) -> str:
        pass
