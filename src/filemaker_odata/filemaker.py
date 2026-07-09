"""Core FileMaker OData client."""

import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence
from urllib.parse import quote
from uuid import uuid4

from filemaker_odata.errors import FileMakerError
from filemaker_odata.operations.base import FileMakerConfig
from filemaker_odata.operations.builder import OperationBuilder
from filemaker_odata.request import RequestProtocol

_COUNT_PATTERN = re.compile(r"^\d+$")
_BOUNDARY_PATTERN = re.compile(r"boundary=(.+?)\r\n")


@dataclass
class RecordsWithCount:
    data: List[dict]
    count: int


@dataclass
class ScriptResult:
    success: bool
    data: Any = None


def _parameterize(
    *,
    select=None,
    top=None,
    skip=None,
    filter=None,
    expand=None,
    order_by=None,
    count=None,
    format=None,
    metadata=None,
) -> str:
    params: dict[str, str] = {}

    if select is not None:
        params["$select"] = ",".join('"' + field.replace('"', '""') + '"' for field in select)
    if top is not None:
        params["$top"] = str(top)
    if skip is not None:
        params["$skip"] = str(skip)
    if filter is not None:
        params["$filter"] = filter
    if expand is not None:
        params["$expand"] = expand
    if order_by:
        clauses = (
            order_by
            if len(order_by) and isinstance(order_by[0], (list, tuple))
            else [order_by]
        )
        params["$orderby"] = ",".join(f'"{key}" {order}' for key, order in clauses)
    if count is not None:
        params["$count"] = "true" if count else "false"

    include_metadata = True if metadata is None else metadata
    fmt = "application/xml" if format == "xml" else "application/json"
    params["$format"] = fmt + ("" if include_metadata else ";odata.metadata=none")

    return "&".join(f"{key}={value}" for key, value in params.items())


class FileMaker:
    def __init__(
        self,
        server: str,
        database: str,
        request: RequestProtocol,
        logger: Optional[logging.Logger] = None,
    ):
        self._config = FileMakerConfig(server=server, database=database)
        self._request = request
        self._logger = logger or logging.getLogger("filemaker_odata")

    def url(self, path: str) -> str:
        return self._config.url(path)

    def metadata(self) -> Any:
        return self._request.get(self.url("$metadata"), response_type="text").data

    def get_records(
        self,
        table: str,
        *,
        select=None,
        top=None,
        skip=None,
        filter=None,
        expand=None,
        order_by=None,
        count=None,
        format=None,
        metadata=None,
    ) -> List[dict]:
        params = _parameterize(
            select=select,
            top=top,
            skip=skip,
            filter=filter,
            expand=expand,
            order_by=order_by,
            count=count,
            format=format,
            metadata=metadata,
        )
        url = f"{self.url(table)}?{params}"
        self._logger.debug("[FileMaker] get_records %s -> %s", table, url)
        return self._request.get(url).data["value"]

    def get_records_with_count(
        self,
        table: str,
        *,
        select=None,
        top=None,
        skip=None,
        filter=None,
        expand=None,
        order_by=None,
        format=None,
        metadata=None,
    ) -> RecordsWithCount:
        params = _parameterize(
            select=select,
            top=top,
            skip=skip,
            filter=filter,
            expand=expand,
            order_by=order_by,
            count=True,
            format=format,
            metadata=metadata,
        )
        url = f"{self.url(table)}?{params}"
        data = self._request.get(url).data
        count = data.get("@odata.count")
        if count is None:
            count = data.get("@count")
        if count is None:
            count = 0
        return RecordsWithCount(data=data["value"], count=count)

    def count_records(self, table: str, *, filter=None) -> int:
        count_path = f"{table}/$count"
        query = f"$filter={filter}" if filter is not None else ""
        url = self.url(count_path if query == "" else f"{count_path}?{query}")
        raw = self._request.get(url, response_type="text").data
        trimmed = raw.strip()
        if not _COUNT_PATTERN.match(trimmed):
            raise FileMakerError(f'Invalid count response from "{count_path}": {raw}')
        return int(trimmed)

    def get_record(
        self,
        table: str,
        id: str,
        *,
        select=None,
        expand=None,
        format=None,
        metadata=None,
    ) -> dict:
        params = _parameterize(
            select=select, expand=expand, format=format, metadata=metadata
        )
        url = f"{self.url(table)}('{quote(str(id), safe='')}')?{params}"
        return self._request.get(url).data

    def get_value(self, table: str, id: str, field: str) -> bytes:
        url = (
            f"{self.url(table)}('{quote(str(id), safe='')}')"
            f"/{quote(str(field), safe='')}/$value"
        )
        return self._request.get(url, response_type="bytes").data

    def subquery(
        self,
        table: str,
        record_id: str,
        path: str,
        *,
        select=None,
        top=None,
        skip=None,
        filter=None,
        expand=None,
        order_by=None,
        count=None,
        format=None,
        metadata=None,
    ) -> List[dict]:
        params = _parameterize(
            select=select,
            top=top,
            skip=skip,
            filter=filter,
            expand=expand,
            order_by=order_by,
            count=count,
            format=format,
            metadata=metadata,
        )
        subpath = f"{table}('{record_id}')/{path}"
        url = f"{self.url(subpath)}?{params}"
        return self._request.get(url).data["value"]

    def crossjoin(
        self, *, tables: Sequence[str], filter=None, expand=None, format=None, metadata=None
    ) -> Any:
        params = _parameterize(
            filter=filter, expand=expand, format=format, metadata=metadata
        )
        url = f"{self.url('$crossjoin')}({','.join(tables)})?{params}"
        return self._request.get(url).data

    def script(self, name: str, params: Optional[dict] = None) -> ScriptResult:
        body = None if params is None else {"scriptParameterValue": params}
        url = self.url(f"Script.{quote(str(name), safe='')}")
        self._logger.debug("[FileMaker] script %s", name)
        data = self._request.post(
            url, body, headers={"Content-Type": "application/json"}
        ).data
        result = data["scriptResult"]
        success = result["code"] == 0
        return ScriptResult(
            success=success, data=result.get("resultParameter") if success else None
        )

    def batch(self) -> OperationBuilder:
        def run(operations):
            batch_boundary = f"batch_{uuid4()}"
            changeset_boundary = f"changeset_{uuid4()}"
            body = (
                f"--{batch_boundary}\r\n"
                f"Content-Type: multipart/mixed; boundary={changeset_boundary}\r\n\r\n"
                + "".join(
                    op.to_request_body(boundary=changeset_boundary, change_id=index + 1)
                    for index, op in enumerate(operations)
                )
                + f"--{changeset_boundary}--\r\n"
                + f"--{batch_boundary}--\r\n"
            )
            response = self._request.post(
                self.url("$batch"),
                body,
                headers={"Content-Type": f"multipart/mixed; boundary={batch_boundary}"},
                response_type="text",
            )
            match = _BOUNDARY_PATTERN.search(response.data)
            if match is None:
                raise FileMakerError("Could not find changeset")
            changeset = match.group(0).split("=")[1].strip()
            changes = response.data.split(f"--{changeset}")[1:-1]
            return [
                operations[index].parse_response(change)
                for index, change in enumerate(changes)
            ]

        return OperationBuilder(self._config, run)
