import json
import re

from filemaker_odata.errors import FileMakerError
from filemaker_odata.operations.base import BatchOperationResponse, FileMakerConfig

_STATUS_PATTERN = re.compile(r"HTTP/1\.1\s+(\d+)\s")


class DeleteOperation:
    def __init__(self, *, config: FileMakerConfig, table: str, id: str):
        self._config = config
        self._table = table
        self._id = id

    def to_request_body(self, *, boundary: str, change_id: int) -> str:
        return (
            f"--{boundary}\r\n"
            "Content-Type: application/http\r\n"
            f"Content-ID: {change_id}\r\n\r\n"
            f"DELETE {self._config.url(self._table)}('{self._id}') HTTP/1.1\r\n\r\n\r\n"
        )

    def parse_response(self, change: str) -> BatchOperationResponse:
        match = _STATUS_PATTERN.search(change)
        if match is None:
            raise FileMakerError("Could not find status in response")
        status = int(match.group(1))
        if status >= 300:
            payload = json.loads(change[change.index("{") :].strip())
            raise FileMakerError(
                f"[DELETE OPERATION: {self._table}] {payload['error']['message']}"
            )
        return BatchOperationResponse(status=status, body=None)
