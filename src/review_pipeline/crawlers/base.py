from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

import pandas as pd


class BaseCrawler(ABC):
    """Abstract crawler interface."""

    name: str = "crawler"

    @abstractmethod
    def fetch(self) -> pd.DataFrame:
        """Fetch reviews and return them as a :class:`pandas.DataFrame`."""


class SupportsLogging(Protocol):
    def debug(self, msg: str, *args, **kwargs) -> None: ...
    def info(self, msg: str, *args, **kwargs) -> None: ...
    def warning(self, msg: str, *args, **kwargs) -> None: ...
    def error(self, msg: str, *args, **kwargs) -> None: ...
