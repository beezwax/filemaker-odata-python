"""Shared types for batch operations."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class FileMakerConfig:
    server: str
    database: str

    def url(self, path: str) -> str:
        return f"https://{self.server}/fmi/odata/v4/{self.database}/{path}"


@dataclass
class BatchOperationResponse:
    status: int
    body: Any


class BatchOperation(Protocol):
    def to_request_body(self, *, boundary: str, change_id: int) -> str: ...

    def parse_response(self, change: str) -> BatchOperationResponse: ...
