import json
import re

from filemaker_odata.errors import FileMakerError
from filemaker_odata.operations.base import BatchOperationResponse, FileMakerConfig

_STATUS_PATTERN = re.compile(r"HTTP/1\.1\s+(\d+)\s")


class CreateOperation:
    def __init__(self, *, config: FileMakerConfig, table: str, record: dict):
        self._config = config
        self._table = table
        self._record = record

    def to_request_body(self, *, boundary: str, change_id: int) -> str:
        body = json.dumps(self._record)
        return (
            f"--{boundary}\r\n"
            "Content-Type: application/http\r\n"
            f"Content-ID: {change_id}\r\n\r\n"
            f"POST {self._config.url(self._table)} HTTP/1.1\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n"
            f"{body}\r\n"
        )

    def parse_response(self, change: str) -> BatchOperationResponse:
        match = _STATUS_PATTERN.search(change)
        if match is None:
            raise FileMakerError("Could not find status in response")
        status = int(match.group(1))
        if status >= 300:
            payload = json.loads(change[change.index("{") :].strip())
            raise FileMakerError(
                f"[CREATE OPERATION: {self._table}] {payload['error']['message']}"
            )
        return BatchOperationResponse(status=status, body=None)
