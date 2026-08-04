from abc import ABC, abstractmethod

from bstockreport.metrics import SourceMetrics


class Source(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...  # pragma: no cover

    @abstractmethod
    def collect(self) -> SourceMetrics: ...  # pragma: no cover
