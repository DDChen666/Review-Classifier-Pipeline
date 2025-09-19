
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List, Sequence


class BaseLabeler(ABC):
    """Interface for automated labelers."""

    @abstractmethod
    def annotate(self, records: Sequence[dict]) -> List[dict]:
        """Return labeled copies of *records*."""

    @abstractmethod
    def validate(self, records: Sequence[dict]) -> List[dict]:
        """Return diagnostics for invalid records (empty if all valid)."""
