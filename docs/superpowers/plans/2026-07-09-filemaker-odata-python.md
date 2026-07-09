# FileMaker OData Python Port — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the TypeScript `filemaker-odata` library to an idiomatic, sync-only Python package (`filemaker_odata`) that talks to FileMaker's OData v4 API.

**Architecture:** A layered client. Pure helpers (`odata`, `errors`) at the bottom; an httpx-backed `Request` layer with pluggable `Credentials`; a core `FileMaker` class that builds OData URLs and parses responses; a fluent batch `operations` package; and a `FileMakerClient` facade for auth setup and OAuth discovery. Records are plain `dict`s. Behavior mirrors the TS source at `/Users/gosukiwi/Beezwax/filemaker-odata` (`src/`, `tests/`).

**Tech Stack:** Python 3.10+, httpx (sync), pytest, managed by uv. `src/` layout, hatchling build backend.

**Design reference:** `docs/superpowers/specs/2026-07-09-filemaker-odata-python-design.md`

**Note on structure:** This plan adds a small `errors.py` module (not in the spec's file list) so `FileMakerError`/`RequestError` have a single home without coupling `operations` → `request`. This is a minor decomposition improvement consistent with the spec's error-hierarchy section.

**Conventions for every task:** Run all commands with `uv run ...`. Commit after each task with the shown message.

---

### Task 1: Project scaffold (uv, pyproject, package skeleton)

**Files:**
- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `src/filemaker_odata/__init__.py`
- Create: `src/filemaker_odata/py.typed` (empty marker)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Pin Python and ensure the toolchain is available**

Run:
```bash
uv python install 3.12
printf '3.12\n' > .python-version
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "filemaker-odata"
version = "0.0.1"
description = "Python client for FileMaker's OData API"
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["httpx>=0.27"]

[dependency-groups]
dev = ["pytest>=8"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/filemaker_odata"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 3: Create the package skeleton**

`src/filemaker_odata/__init__.py`:
```python
"""Python client for FileMaker's OData API."""

import logging

# Keep the library silent unless the application configures logging.
logging.getLogger("filemaker_odata").addHandler(logging.NullHandler())
```

Create empty files `src/filemaker_odata/py.typed` and `tests/__init__.py`.

Also create a placeholder README so the build backend is happy:
```bash
printf '# FileMaker OData (Python)\n' > README.md
```

- [ ] **Step 4: Sync and verify the package imports**

Run:
```bash
uv sync
uv run python -c "import httpx, filemaker_odata; print('ok', httpx.__version__)"
```
Expected: prints `ok <version>` with no traceback.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: scaffold uv project and filemaker_odata package"
```

---

### Task 2: OData escaping helpers (`odata.py`)

**Files:**
- Create: `src/filemaker_odata/odata.py`
- Test: `tests/test_odata.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_odata.py`:
```python
import pytest

from filemaker_odata import odata


class TestString:
    def test_wraps_values_in_single_quotes(self):
        assert odata.string("Beezwax") == "'Beezwax'"

    def test_escapes_single_quotes_by_doubling(self):
        assert odata.string("O'Brien") == "'O''Brien'"

    def test_does_not_url_encode_the_literal(self):
        assert odata.string("A B&C") == "'A B&C'"

    def test_rejects_non_string_values(self):
        with pytest.raises(TypeError, match="Invalid OData string"):
            odata.string(True)


class TestNumber:
    def test_accepts_finite_numbers(self):
        assert odata.number(42) == "42"
        assert odata.number(-12.5) == "-12.5"

    def test_accepts_numeric_strings(self):
        assert odata.number("42") == "42"
        assert odata.number("  -12.5  ") == "-12.5"

    def test_canonicalizes_non_standard_string_forms(self):
        assert odata.number("+42") == "42"
        assert odata.number("01") == "1"
        assert odata.number(".5") == "0.5"

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), "", "12abc", True, None, {}])
    def test_rejects_invalid_numbers(self, value):
        with pytest.raises(TypeError, match="Invalid OData number"):
            odata.number(value)


class TestInteger:
    def test_accepts_integers(self):
        assert odata.integer(42) == "42"
        assert odata.integer(" -12 ") == "-12"

    @pytest.mark.parametrize("value", [12.5, "12.5", True, None, {}])
    def test_rejects_non_integers(self, value):
        with pytest.raises(TypeError, match="Invalid OData integer"):
            odata.integer(value)


class TestBoolean:
    def test_accepts_booleans(self):
        assert odata.boolean(True) == "true"
        assert odata.boolean(False) == "false"

    def test_rejects_non_boolean_values(self):
        with pytest.raises(TypeError, match="Invalid OData boolean"):
            odata.boolean("true")


class TestUuid:
    def test_accepts_valid_uuid(self):
        assert odata.uuid("280dc895-23f6-4368-be3b-3ea81d360f62") == (
            "'280dc895-23f6-4368-be3b-3ea81d360f62'"
        )

    def test_accepts_uuidv7(self):
        assert odata.uuid("0196f682-e18d-7000-8000-000000000000") == (
            "'0196f682-e18d-7000-8000-000000000000'"
        )

    @pytest.mark.parametrize(
        "value",
        ["not-a-uuid", "0196f682-e18d-7000-7000-000000000000", True],
    )
    def test_rejects_bad_uuids(self, value):
        with pytest.raises(TypeError, match="Invalid OData UUID"):
            odata.uuid(value)


class TestIdentifier:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("NAME", '"NAME"'),
            ("Customer Name", '"Customer Name"'),
            ("customer_id", '"customer_id"'),
            ("Order-Number", '"Order-Number"'),
        ],
    )
    def test_quotes_safe_identifiers(self, value, expected):
        assert odata.identifier(value) == expected

    @pytest.mark.parametrize(
        "value", ['NA"ME', "Orders/ID", "NAME)&$top=1", "", True, 123]
    )
    def test_rejects_unsafe_identifiers(self, value):
        with pytest.raises(TypeError, match="Invalid OData identifier"):
            odata.identifier(value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_odata.py -q`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError` (no `odata` helpers yet).

- [ ] **Step 3: Implement `src/filemaker_odata/odata.py`**

```python
"""Helpers for safely building OData literals from untrusted input.

Each helper raises ``TypeError`` with a stable message on invalid input, so the
library behaves the same whether or not callers use type checking.
"""

import math
import re

_NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+|\d+\.\d+|\.\d+)$")
_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9 _-]+$")


def _num_to_str(value: float) -> str:
    """Mirror JavaScript ``String(Number(...))``: integral floats lose the ``.0``."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return str(number)


def string(value) -> str:
    if not isinstance(value, str):
        raise TypeError("Invalid OData string")
    return "'" + value.replace("'", "''") + "'"


def number(value) -> str:
    if isinstance(value, bool):
        raise TypeError("Invalid OData number")
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise TypeError("Invalid OData number")
        return _num_to_str(value)
    if not isinstance(value, str):
        raise TypeError("Invalid OData number")
    normalized = value.strip()
    if not _NUMBER_PATTERN.match(normalized):
        raise TypeError("Invalid OData number")
    parsed = float(normalized)
    if not math.isfinite(parsed):
        raise TypeError("Invalid OData number")
    return _num_to_str(parsed)


def integer(value) -> str:
    if isinstance(value, bool):
        raise TypeError("Invalid OData integer")
    if not isinstance(value, (int, float, str)):
        raise TypeError("Invalid OData integer")
    normalized = _num_to_str(value) if isinstance(value, (int, float)) else value.strip()
    if not _INTEGER_PATTERN.match(normalized):
        raise TypeError("Invalid OData integer")
    return normalized


def boolean(value) -> str:
    if not isinstance(value, bool):
        raise TypeError("Invalid OData boolean")
    return "true" if value else "false"


def uuid(value) -> str:
    if not isinstance(value, str):
        raise TypeError("Invalid OData UUID")
    if not _UUID_PATTERN.match(value):
        raise TypeError("Invalid OData UUID")
    return string(value)


def identifier(value) -> str:
    if not isinstance(value, str):
        raise TypeError("Invalid OData identifier")
    if not _IDENTIFIER_PATTERN.match(value):
        raise TypeError("Invalid OData identifier")
    return '"' + value + '"'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_odata.py -q`
Expected: PASS (all cases).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add odata escaping helpers"
```

---

### Task 3: Errors and credentials (`errors.py`, `credentials.py`)

**Files:**
- Create: `src/filemaker_odata/errors.py`
- Create: `src/filemaker_odata/credentials.py`
- Test: `tests/test_credentials.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_credentials.py`:
```python
import base64

from filemaker_odata.credentials import (
    BasicCredentials,
    NullCredentials,
    OAuthCredentials,
    RawCredentials,
)


def test_null_credentials_have_no_headers():
    assert NullCredentials().authorization_headers == {}


def test_basic_credentials_base64_encode_user_and_pass():
    creds = BasicCredentials(username="my-user", password="my-pass")
    expected = base64.b64encode(b"my-user:my-pass").decode("ascii")
    assert creds.authorization_headers == {"Authorization": f"Basic {expected}"}


def test_oauth_credentials_emit_fm_headers():
    creds = OAuthCredentials(request_id="req-1", identifier="id-1")
    assert creds.authorization_headers == {
        "OData-Version": "4.0",
        "OData-MaxVersion": "4.0",
        "X-FM-Data-OAuth-Request-Id": "req-1",
        "X-FM-Data-OAuth-Identifier": "id-1",
    }


def test_raw_credentials_pass_through_authorization():
    creds = RawCredentials("Basic abc123")
    assert creds.authorization_headers == {"Authorization": "Basic abc123"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_credentials.py -q`
Expected: FAIL — `ModuleNotFoundError: filemaker_odata.credentials`.

- [ ] **Step 3: Implement `src/filemaker_odata/errors.py`**

```python
"""Exception hierarchy for the FileMaker OData client."""


class FileMakerError(Exception):
    """Base class for all errors raised by this library."""


class RequestError(FileMakerError):
    """Raised when an HTTP request to FileMaker fails.

    ``data`` holds the response body when one is available, else ``None``.
    """

    def __init__(self, message: str, *, data=None):
        super().__init__(message)
        self.data = data
```

- [ ] **Step 4: Implement `src/filemaker_odata/credentials.py`**

```python
"""Authorization strategies for FileMaker requests."""

import base64
from typing import Protocol, runtime_checkable


@runtime_checkable
class Credentials(Protocol):
    @property
    def authorization_headers(self) -> dict[str, str]:
        """Headers to attach to every request for this strategy."""
        ...


class NullCredentials:
    """No authorization headers (used for anonymous discovery endpoints)."""

    @property
    def authorization_headers(self) -> dict[str, str]:
        return {}


class BasicCredentials:
    def __init__(self, *, username: str, password: str):
        self._username = username
        self._password = password

    @property
    def authorization_headers(self) -> dict[str, str]:
        token = base64.b64encode(
            f"{self._username}:{self._password}".encode("utf-8")
        ).decode("ascii")
        return {"Authorization": f"Basic {token}"}


class OAuthCredentials:
    def __init__(self, *, request_id: str, identifier: str):
        self._request_id = request_id
        self._identifier = identifier

    @property
    def authorization_headers(self) -> dict[str, str]:
        return {
            "OData-Version": "4.0",
            "OData-MaxVersion": "4.0",
            "X-FM-Data-OAuth-Request-Id": self._request_id,
            "X-FM-Data-OAuth-Identifier": self._identifier,
        }


class RawCredentials:
    """Passes a raw value straight to the ``Authorization`` header."""

    def __init__(self, authorization: str):
        self._authorization = authorization

    @property
    def authorization_headers(self) -> dict[str, str]:
        return {"Authorization": self._authorization}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_credentials.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add error hierarchy and credential strategies"
```

---

### Task 4: HTTP request layer (`request.py`)

**Files:**
- Create: `src/filemaker_odata/request.py`
- Test: `tests/test_request.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_request.py`:
```python
import httpx
import pytest

from filemaker_odata.credentials import BasicCredentials, NullCredentials
from filemaker_odata.errors import RequestError
from filemaker_odata.request import Request, Response


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_get_parses_json_and_sends_auth_headers():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"value": [1, 2]})

    req = Request(BasicCredentials(username="u", password="p"), client=_client(handler))
    response = req.get("https://example.test/x")

    assert isinstance(response, Response)
    assert response.data == {"value": [1, 2]}
    assert captured["auth"].startswith("Basic ")


def test_get_text_response_type_returns_str():
    def handler(request):
        return httpx.Response(200, text=" 29\n")

    req = Request(NullCredentials(), client=_client(handler))
    response = req.get("https://example.test/count", response_type="text")
    assert response.data == " 29\n"


def test_get_bytes_response_type_returns_bytes():
    def handler(request):
        return httpx.Response(200, content=b"\x00\x01\x02")

    req = Request(NullCredentials(), client=_client(handler))
    response = req.get("https://example.test/blob", response_type="bytes")
    assert response.data == b"\x00\x01\x02"


def test_get_raises_request_error_carrying_response_body():
    def handler(request):
        return httpx.Response(404, json={"error": {"message": "nope"}})

    req = Request(NullCredentials(), client=_client(handler))
    with pytest.raises(RequestError) as excinfo:
        req.get("https://example.test/missing")
    assert excinfo.value.data == {"error": {"message": "nope"}}


def test_post_json_body_sets_content_and_returns_data():
    captured = {}

    def handler(request):
        captured["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    req = Request(NullCredentials(), client=_client(handler))
    response = req.post("https://example.test/x", {"a": 1})
    assert response.data == {"ok": True}
    assert b'"a"' in captured["body"]


def test_post_string_body_sent_as_content():
    captured = {}

    def handler(request):
        captured["body"] = request.content
        return httpx.Response(200, text="ok")

    req = Request(NullCredentials(), client=_client(handler))
    req.post("https://example.test/x", "raw-body", response_type="text")
    assert captured["body"] == b"raw-body"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_request.py -q`
Expected: FAIL — `ModuleNotFoundError: filemaker_odata.request`.

- [ ] **Step 3: Implement `src/filemaker_odata/request.py`**

```python
"""httpx-backed HTTP layer with pluggable credentials."""

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, Union

import httpx

from filemaker_odata.credentials import Credentials
from filemaker_odata.errors import RequestError

# Re-exported for callers that catch errors from this module.
__all__ = ["Response", "Request", "RequestError", "RequestProtocol"]

ResponseType = str  # one of: "json", "text", "bytes"
PostBody = Union[str, bytes, Mapping[str, Any], None]


@dataclass
class Response:
    data: Any
    headers: Mapping[str, str]


class RequestProtocol(Protocol):
    """The surface ``FileMaker`` depends on (real or mocked)."""

    def get(
        self, url: str, *, headers: Optional[dict] = None, response_type: ResponseType = "json"
    ) -> Response: ...

    def post(
        self,
        url: str,
        body: PostBody,
        *,
        headers: Optional[dict] = None,
        response_type: ResponseType = "json",
    ) -> Response: ...


def _parse(response: httpx.Response, response_type: ResponseType) -> Any:
    if response_type == "text":
        return response.text
    if response_type == "bytes":
        return response.content
    return response.json()


def _safe_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except Exception:
        return response.text


class Request:
    """Executes HTTP requests, attaching credential headers to each call.

    ``client`` is the analogue of the TS ``agent`` — pass a configured
    ``httpx.Client`` for custom TLS/proxy behavior or tests.
    """

    def __init__(self, credentials: Credentials, client: Optional[httpx.Client] = None):
        self._credentials = credentials
        self._client = client or httpx.Client()

    def get(self, url, *, headers=None, response_type="json") -> Response:
        return self._request("GET", url, None, headers, response_type)

    def post(self, url, body, *, headers=None, response_type="json") -> Response:
        return self._request("POST", url, body, headers, response_type)

    def _request(self, method, url, body, headers, response_type) -> Response:
        merged = {**self._credentials.authorization_headers, **(headers or {})}
        kwargs: dict[str, Any] = {"headers": merged}
        if body is not None:
            if isinstance(body, (str, bytes)):
                kwargs["content"] = body
            else:
                kwargs["json"] = body
        try:
            response = self._client.request(method, url, **kwargs)
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise RequestError(str(error), data=_safe_body(error.response)) from error
        except httpx.HTTPError as error:
            raise RequestError(str(error), data=None) from error
        return Response(data=_parse(response, response_type), headers=response.headers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_request.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add httpx request layer with Response and RequestError"
```

---

### Task 5: Batch operations (`operations/`)

**Files:**
- Create: `src/filemaker_odata/operations/__init__.py` (empty)
- Create: `src/filemaker_odata/operations/base.py`
- Create: `src/filemaker_odata/operations/create.py`
- Create: `src/filemaker_odata/operations/update.py`
- Create: `src/filemaker_odata/operations/delete.py`
- Create: `src/filemaker_odata/operations/builder.py`
- Test: `tests/test_operations.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_operations.py`:
```python
import pytest

from filemaker_odata.errors import FileMakerError
from filemaker_odata.operations.base import BatchOperationResponse, FileMakerConfig
from filemaker_odata.operations.builder import OperationBuilder
from filemaker_odata.operations.create import CreateOperation
from filemaker_odata.operations.delete import DeleteOperation
from filemaker_odata.operations.update import UpdateOperation

CONFIG = FileMakerConfig(server="demo.server.beezwax.net", database="test")


def test_config_builds_odata_url():
    assert CONFIG.url("FINDING") == (
        "https://demo.server.beezwax.net/fmi/odata/v4/test/FINDING"
    )


def test_create_request_body_contains_post_and_json():
    op = CreateOperation(config=CONFIG, table="FINDING", record={"FINDING": "body"})
    body = op.to_request_body(boundary="cs", change_id=1)
    assert "--cs\r\n" in body
    assert "Content-ID: 1\r\n" in body
    assert f"POST {CONFIG.url('FINDING')} HTTP/1.1\r\n" in body
    assert '{"FINDING": "body"}' in body


def test_create_parse_response_success():
    change = "\r\nHTTP/1.1 201 Created\r\n\r\n"
    assert op_create().parse_response(change) == BatchOperationResponse(status=201, body=None)


def test_create_parse_response_error_raises():
    change = 'HTTP/1.1 500 Error\r\n\r\n{"error":{"code":"1","message":"bad"}}'
    with pytest.raises(FileMakerError, match=r"\[CREATE OPERATION: FINDING\] bad"):
        op_create().parse_response(change)


def test_update_strips_id_and_targets_record():
    op = UpdateOperation(
        config=CONFIG, table="FINDING", record={"ID": "F-1", "FINDING": "x"}
    )
    body = op.to_request_body(boundary="cs", change_id=2)
    assert f"PATCH {CONFIG.url('FINDING')}('F-1') HTTP/1.1\r\n" in body
    assert '{"FINDING": "x"}' in body
    assert '"ID"' not in body


def test_update_parse_response_returns_json_body():
    change = 'HTTP/1.1 200 OK\r\n\r\n{"ID":"F-1","FINDING":"x"}'
    op = UpdateOperation(config=CONFIG, table="FINDING", record={"ID": "F-1"})
    assert op.parse_response(change) == BatchOperationResponse(
        status=200, body={"ID": "F-1", "FINDING": "x"}
    )


def test_delete_request_body_and_success():
    op = DeleteOperation(config=CONFIG, table="FINDING", id="F-1")
    body = op.to_request_body(boundary="cs", change_id=3)
    assert f"DELETE {CONFIG.url('FINDING')}('F-1') HTTP/1.1\r\n" in body
    change = "HTTP/1.1 204 No Content\r\n\r\n"
    assert op.parse_response(change) == BatchOperationResponse(status=204, body=None)


def test_builder_collects_operations_and_calls_back():
    seen = {}

    def callback(operations):
        seen["ops"] = operations
        return ["result"]

    result = (
        OperationBuilder(CONFIG, callback)
        .create(table="T", record={"a": 1})
        .update(table="T", record={"ID": "1"})
        .delete(table="T", id="1")
        .execute()
    )
    assert result == ["result"]
    assert [type(o).__name__ for o in seen["ops"]] == [
        "CreateOperation",
        "UpdateOperation",
        "DeleteOperation",
    ]


def op_create():
    return CreateOperation(config=CONFIG, table="FINDING", record={"FINDING": "body"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_operations.py -q`
Expected: FAIL — `ModuleNotFoundError: filemaker_odata.operations.base`.

- [ ] **Step 3: Implement `src/filemaker_odata/operations/base.py`**

```python
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
```

Create empty `src/filemaker_odata/operations/__init__.py`.

- [ ] **Step 4: Implement the three operations**

`src/filemaker_odata/operations/create.py`:
```python
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
```

`src/filemaker_odata/operations/update.py`:
```python
import json
import re

from filemaker_odata.errors import FileMakerError
from filemaker_odata.operations.base import BatchOperationResponse, FileMakerConfig

_STATUS_PATTERN = re.compile(r"HTTP/1\.1\s+(\d+)\s")


class UpdateOperation:
    def __init__(self, *, config: FileMakerConfig, table: str, record: dict):
        self._config = config
        self._table = table
        self._record = record

    def to_request_body(self, *, boundary: str, change_id: int) -> str:
        record = dict(self._record)
        record_id = record.pop("ID")
        body = json.dumps(record)
        return (
            f"--{boundary}\r\n"
            "Content-Type: application/http\r\n"
            f"Content-ID: {change_id}\r\n\r\n"
            f"PATCH {self._config.url(self._table)}('{record_id}') HTTP/1.1\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n"
            f"{body}\r\n"
        )

    def parse_response(self, change: str) -> BatchOperationResponse:
        match = _STATUS_PATTERN.search(change)
        if match is None:
            raise FileMakerError("Could not find status in response")
        status = int(match.group(1))
        payload = json.loads(change[change.index("{") :].strip())
        if status >= 300:
            raise FileMakerError(
                f"[UPDATE OPERATION: {self._table}] {payload['error']['message']}"
            )
        return BatchOperationResponse(status=status, body=payload)
```

`src/filemaker_odata/operations/delete.py`:
```python
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
```

- [ ] **Step 5: Implement `src/filemaker_odata/operations/builder.py`**

```python
from typing import Callable, List

from filemaker_odata.operations.base import (
    BatchOperation,
    BatchOperationResponse,
    FileMakerConfig,
)
from filemaker_odata.operations.create import CreateOperation
from filemaker_odata.operations.delete import DeleteOperation
from filemaker_odata.operations.update import UpdateOperation

BatchCallback = Callable[[List[BatchOperation]], List[BatchOperationResponse]]


class OperationBuilder:
    """Collects batch operations, then runs them via ``execute()``."""

    def __init__(self, config: FileMakerConfig, callback: BatchCallback):
        self._config = config
        self._callback = callback
        self._operations: List[BatchOperation] = []

    def create(self, *, table: str, record: dict) -> "OperationBuilder":
        self._operations.append(CreateOperation(config=self._config, table=table, record=record))
        return self

    def update(self, *, table: str, record: dict) -> "OperationBuilder":
        self._operations.append(UpdateOperation(config=self._config, table=table, record=record))
        return self

    def delete(self, *, table: str, id: str) -> "OperationBuilder":
        self._operations.append(DeleteOperation(config=self._config, table=table, id=id))
        return self

    def execute(self) -> List[BatchOperationResponse]:
        return self._callback(self._operations)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_operations.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add batch operations and fluent builder"
```

---

### Task 6: Core `FileMaker` client (`filemaker.py`) + test mock

**Files:**
- Create: `src/filemaker_odata/filemaker.py`
- Create: `tests/mocks.py`
- Test: `tests/test_filemaker.py`

- [ ] **Step 1: Write the test mock**

`tests/mocks.py`:
```python
from filemaker_odata.request import Response


class MockRequest:
    """Registers canned responses by (method, url); records the last call."""

    def __init__(self):
        self._responses = {"GET": {}, "POST": {}}
        self._calls = []

    def mock(self, *, type, url, data, headers=None):
        self._responses[type][url] = Response(data=data, headers=headers or {})

    def get(self, url, *, headers=None, response_type="json"):
        response = self._responses["GET"].get(url)
        if response is None:
            raise AssertionError(f'Could not find mock GET request: "{url}"')
        self._calls.append(
            {"type": "GET", "url": url, "headers": headers, "response_type": response_type}
        )
        return response

    def post(self, url, body, *, headers=None, response_type="json"):
        response = self._responses["POST"].get(url)
        if response is None:
            raise AssertionError(f'Could not find mock POST request: "{url}"')
        self._calls.append(
            {
                "type": "POST",
                "url": url,
                "body": body,
                "headers": headers,
                "response_type": response_type,
            }
        )
        return response

    def latest_request(self):
        return self._calls[-1] if self._calls else None
```

- [ ] **Step 2: Write the failing tests**

`tests/test_filemaker.py`:
```python
import pytest

from filemaker_odata import odata
from filemaker_odata.errors import FileMakerError
from filemaker_odata.filemaker import FileMaker, RecordsWithCount, ScriptResult
from tests.mocks import MockRequest


def fixtures():
    request = MockRequest()
    fm = FileMaker(server="demo.server.beezwax.net", database="test", request=request)
    return fm, request


def test_url():
    fm, _ = fixtures()
    assert fm.url("foo") == "https://demo.server.beezwax.net/fmi/odata/v4/test/foo"


def test_metadata():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("$metadata"), data="someJSON")
    assert fm.metadata() == "someJSON"


def test_get_records_no_options():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$format=application/json"),
        data={"value": [{"ID": "1234", "NAME": "Fede", "COMPANY": "Beezwax"}]},
    )
    records = fm.get_records("people")
    assert len(records) == 1
    assert records[0]["NAME"] == "Fede"


def test_get_records_select_single():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$select="NAME"&$format=application/json'),
        data={"value": [{"NAME": "Fede"}]},
    )
    assert fm.get_records("people", select=["NAME"])[0]["NAME"] == "Fede"


def test_get_records_select_multiple():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$select="ID","NAME","COMPANY"&$format=application/json'),
        data={"value": [{"ID": "1234", "NAME": "Fede", "COMPANY": "Beezwax"}]},
    )
    assert fm.get_records("people", select=["ID", "NAME", "COMPANY"])[0]["ID"] == "1234"


def test_get_records_top_skip():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=5&$skip=10&$format=application/json"),
        data={"value": [{"ID": "11"}]},
    )
    assert fm.get_records("people", top=5, skip=10)[0]["ID"] == "11"


def test_get_records_filter_raw_and_escaped():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$filter=name eq 'O''Brien'&$format=application/json"),
        data={"value": [{"NAME": "O'Brien"}]},
    )
    literal = odata.string("O'Brien")  # -> 'O''Brien'
    records = fm.get_records("people", filter=f"name eq {literal}")
    assert records[0]["NAME"] == "O'Brien"


def test_get_records_expand():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$expand=orders&$format=application/json"),
        data={"value": [{"ID": "1234"}]},
    )
    assert len(fm.get_records("people", expand="orders")) == 1


def test_get_records_orderby_single():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$orderby="NAME" asc&$format=application/json'),
        data={"value": [{"NAME": "Alice"}, {"NAME": "Bob"}]},
    )
    assert fm.get_records("people", order_by=("NAME", "asc"))[0]["NAME"] == "Alice"


def test_get_records_orderby_multiple():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$orderby="COMPANY" asc,"NAME" desc&$format=application/json'),
        data={"value": [{"COMPANY": "Acme Corp", "NAME": "Zara"}]},
    )
    records = fm.get_records("people", order_by=[("COMPANY", "asc"), ("NAME", "desc")])
    assert records[0]["NAME"] == "Zara"


@pytest.mark.parametrize("flag,text", [(True, "true"), (False, "false")])
def test_get_records_count_flag(flag, text):
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url(f"people?$count={text}&$format=application/json"),
        data={"value": [{"ID": "1234"}]},
    )
    assert len(fm.get_records("people", count=flag)) == 1


def test_get_records_combined_options():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url(
            'people?$select="NAME","COMPANY"&$top=10&$skip=5'
            "&$filter=company eq 'Beezwax'&$orderby=\"NAME\" asc&$format=application/json"
        ),
        data={"value": [{"NAME": "Fede", "COMPANY": "Beezwax"}]},
    )
    records = fm.get_records(
        "people",
        select=["NAME", "COMPANY"],
        top=10,
        skip=5,
        filter="company eq 'Beezwax'",
        order_by=("NAME", "asc"),
    )
    assert records[0]["COMPANY"] == "Beezwax"


def test_get_records_metadata_false_appends_suffix():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$format=application/json;odata.metadata=none"),
        data={"value": []},
    )
    assert fm.get_records("people", metadata=False) == []


def test_get_records_with_count_reads_odata_count():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=1&$count=true&$format=application/json"),
        data={"@odata.count": 29, "value": [{"ID": "1234"}]},
    )
    result = fm.get_records_with_count("people", top=1)
    assert isinstance(result, RecordsWithCount)
    assert result.count == 29
    assert len(result.data) == 1


def test_get_records_with_count_reads_fm_count():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=1&$count=true&$format=application/json"),
        data={"@count": 29, "value": [{"ID": "1234"}]},
    )
    assert fm.get_records_with_count("people", top=1).count == 29


def test_get_records_with_count_defaults_zero():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=1&$count=true&$format=application/json"),
        data={"value": [{"ID": "1234"}]},
    )
    assert fm.get_records_with_count("people", top=1).count == 0


def test_count_records_endpoint_and_response_type():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("people/$count"), data="29")
    assert fm.count_records("people") == 29
    assert request.latest_request()["response_type"] == "text"


def test_count_records_with_filter():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people/$count?$filter=company eq 'Beezwax'"),
        data="12",
    )
    assert fm.count_records("people", filter="company eq 'Beezwax'") == 12


def test_count_records_trims_whitespace():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("people/$count"), data=" 29\n")
    assert fm.count_records("people") == 29


def test_count_records_rejects_non_numeric():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("people/$count"), data="twenty-nine")
    with pytest.raises(FileMakerError, match=r'Invalid count response from "people/\$count": twenty-nine'):
        fm.count_records("people")


def test_get_record_by_id():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('1234')?$format=application/json"),
        data={"ID": "1234", "NAME": "Fede"},
    )
    assert fm.get_record("people", "1234")["NAME"] == "Fede"


def test_get_record_encodes_special_chars():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('test%40example.com')?$format=application/json"),
        data={"ID": "test@example.com"},
    )
    assert fm.get_record("people", "test@example.com")["ID"] == "test@example.com"


def test_get_value_returns_bytes():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('1234')/PHOTO/$value"),
        data=b"\x89PNG",
    )
    assert fm.get_value("people", "1234", "PHOTO") == b"\x89PNG"
    assert request.latest_request()["response_type"] == "bytes"


def test_subquery_returns_value_list():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('1234')/orders?$format=application/json"),
        data={"value": [{"ID": "o1"}]},
    )
    assert fm.subquery("people", "1234", "orders")[0]["ID"] == "o1"


def test_crossjoin_builds_url():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("$crossjoin(people,orders)?$format=application/json"),
        data={"value": []},
    )
    assert fm.crossjoin(tables=["people", "orders"]) == {"value": []}


def test_script_success():
    fm, request = fixtures()
    request.mock(
        type="POST",
        url=fm.url("Script.MyScript"),
        data={"scriptResult": {"code": 0, "resultParameter": {"ok": 1}}},
    )
    result = fm.script("MyScript", {"foo": "bar"})
    assert result == ScriptResult(success=True, data={"ok": 1})
    assert request.latest_request()["body"] == {"scriptParameterValue": {"foo": "bar"}}


def test_script_failure_returns_no_data():
    fm, request = fixtures()
    request.mock(
        type="POST",
        url=fm.url("Script.MyScript"),
        data={"scriptResult": {"code": 5, "resultParameter": {"ignored": 1}}},
    )
    result = fm.script("MyScript")
    assert result == ScriptResult(success=False, data=None)
    assert request.latest_request()["body"] is None


def test_batch_executes_and_parses_changeset():
    fm, request = fixtures()
    changeset_response = (
        "--batchresponse_1\r\n"
        "Content-Type: multipart/mixed; boundary=changesetresponse_1\r\n\r\n"
        "--changesetresponse_1\r\n"
        "Content-Type: application/http\r\n\r\n"
        'HTTP/1.1 200 OK\r\n\r\n{"ID":"F-1","FINDING":"updated"}\r\n'
        "--changesetresponse_1--\r\n"
        "--batchresponse_1--\r\n"
    )
    request.mock(type="POST", url=fm.url("$batch"), data=changeset_response)

    results = fm.batch().update(table="FINDING", record={"ID": "F-1", "FINDING": "updated"}).execute()

    assert len(results) == 1
    assert results[0].status == 200
    assert results[0].body == {"ID": "F-1", "FINDING": "updated"}
    assert request.latest_request()["headers"]["Content-Type"].startswith(
        "multipart/mixed; boundary=batch_"
    )
```

Note: `test_batch_executes_and_parses_changeset` exercises the full multipart round-trip; the mocked `$batch` response uses server-side boundary names (`changesetresponse_1`) that the parser discovers from the response body, independent of the request-side `batch_<uuid>` boundaries.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_filemaker.py -q`
Expected: FAIL — `ModuleNotFoundError: filemaker_odata.filemaker`.

- [ ] **Step 4: Implement `src/filemaker_odata/filemaker.py`**

```python
"""Core FileMaker OData client."""

import logging
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple, Union
from urllib.parse import quote
from uuid import uuid4

from filemaker_odata.errors import FileMakerError
from filemaker_odata.operations.base import FileMakerConfig
from filemaker_odata.operations.builder import OperationBuilder
from filemaker_odata.request import RequestProtocol

OrderClause = Tuple[str, str]
OrderBy = Union[OrderClause, Sequence[OrderClause]]

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
    if order_by is not None:
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
        count = data.get("@odata.count", data.get("@count", 0))
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
        url = f"{self.url(f\"{table}('{record_id}')/{path}\")}?{params}"
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_filemaker.py -q`
Expected: PASS (all cases).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add core FileMaker client with query, count, script, and batch"
```

---

### Task 7: `FileMakerClient` facade (`client.py`)

**Files:**
- Create: `src/filemaker_odata/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_client.py`:
```python
import httpx
import pytest

from filemaker_odata.client import FileMakerClient, OAuthUrl
from filemaker_odata.errors import FileMakerError
from filemaker_odata.filemaker import FileMaker


def client_with(handler):
    return FileMakerClient(
        server="demo.server.beezwax.net",
        database="test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_url():
    client = FileMakerClient(server="demo.server.beezwax.net", database="test")
    assert client.url("foo") == "https://demo.server.beezwax.net/fmi/odata/v4/test/foo"


def test_with_basic_auth_returns_filemaker():
    client = FileMakerClient(server="s", database="d")
    assert isinstance(client.with_basic_auth(username="u", password="p"), FileMaker)


def test_with_oauth_returns_filemaker():
    client = FileMakerClient(server="s", database="d")
    assert isinstance(client.with_oauth(request_id="r", identifier="i"), FileMaker)


def test_get_oauth_url_reads_redirect_and_request_id():
    def handler(request):
        return httpx.Response(
            200, text="https://redirect.example", headers={"x-fms-request-id": "abc"}
        )

    result = client_with(handler).get_oauth_url(tracking_id="t", provider="Google")
    assert result == OAuthUrl(redirect_url="https://redirect.example", request_id="abc")


def test_get_oauth_url_raises_without_request_id_header():
    def handler(request):
        return httpx.Response(200, text="https://redirect.example")

    with pytest.raises(FileMakerError, match="X-FMS-Request-ID"):
        client_with(handler).get_oauth_url(tracking_id="t", provider="Google")


def test_get_auth_types_returns_provider_names():
    def handler(request):
        return httpx.Response(200, json={"data": {"Provider": [{"Name": "Google"}, {"Name": "Amazon"}]}})

    assert client_with(handler).get_auth_types() == ["Google", "Amazon"]


def test_get_auth_types_falls_back_to_basic():
    def handler(request):
        return httpx.Response(200, json={})

    assert client_with(handler).get_auth_types() == ["basic"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py -q`
Expected: FAIL — `ModuleNotFoundError: filemaker_odata.client`.

- [ ] **Step 3: Implement `src/filemaker_odata/client.py`**

```python
"""Facade for creating configured FileMaker clients and OAuth discovery."""

import logging
from dataclasses import dataclass
from typing import List, Optional

import httpx

from filemaker_odata.credentials import (
    BasicCredentials,
    Credentials,
    NullCredentials,
    OAuthCredentials,
)
from filemaker_odata.errors import FileMakerError
from filemaker_odata.filemaker import FileMaker
from filemaker_odata.request import Request


@dataclass
class OAuthUrl:
    redirect_url: str
    request_id: str


class FileMakerClient:
    def __init__(
        self,
        server: str,
        database: str,
        *,
        http_client: Optional[httpx.Client] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self._server = server
        self._database = database
        self._http_client = http_client
        self._logger = logger

    def url(self, path: str) -> str:
        return f"https://{self._server}/fmi/odata/v4/{self._database}/{path}"

    def _make(self, credentials: Credentials) -> FileMaker:
        request = Request(credentials, client=self._http_client)
        return FileMaker(self._server, self._database, request, logger=self._logger)

    def with_basic_auth(self, *, username: str, password: str) -> FileMaker:
        return self._make(BasicCredentials(username=username, password=password))

    def with_oauth(self, *, request_id: str, identifier: str) -> FileMaker:
        return self._make(OAuthCredentials(request_id=request_id, identifier=identifier))

    def get_oauth_url(
        self, *, tracking_id: str, provider: str, return_url: Optional[str] = None
    ) -> OAuthUrl:
        request = Request(NullCredentials(), client=self._http_client)
        url = (
            f"https://{self._server}/oauth/getoauthurl"
            f"?trackingID={tracking_id}&provider={provider}"
            f"&address={self._server}&X-FMS-OAuth-AuthType=2"
        )
        response = request.get(
            url,
            headers={
                "X-FMS-Application-Type": "9",
                "X-FMS-Application-Version": "15",
                "X-FMS-Return-URL": return_url or f"https://{self._server}/oauth-handler",
            },
            response_type="text",
        )
        request_id = response.headers.get("x-fms-request-id", "")
        if not request_id:
            raise FileMakerError(
                'Did not get back an "X-FMS-Request-ID" header from FileMaker'
            )
        return OAuthUrl(redirect_url=response.data, request_id=request_id)

    def get_auth_types(self) -> List[str]:
        request = Request(NullCredentials(), client=self._http_client)
        response = request.get(
            f"https://{self._server}/fmws/oauthproviderinfo",
            headers={"Content-Type": "application/json"},
        )
        payload = response.data.get("data")
        if payload is not None:
            return [provider["Name"] for provider in payload["Provider"]]
        return ["basic"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: add FileMakerClient facade with OAuth discovery"
```

---

### Task 8: Public exports, README, full suite

**Files:**
- Modify: `src/filemaker_odata/__init__.py`
- Modify: `README.md`
- Test: `tests/test_public_api.py`

- [ ] **Step 1: Write the failing test**

`tests/test_public_api.py`:
```python
import filemaker_odata as fm


def test_public_exports_present():
    names = [
        "FileMakerClient",
        "FileMaker",
        "RecordsWithCount",
        "ScriptResult",
        "OAuthUrl",
        "Credentials",
        "NullCredentials",
        "BasicCredentials",
        "OAuthCredentials",
        "RawCredentials",
        "Request",
        "Response",
        "RequestError",
        "FileMakerError",
        "BatchOperationResponse",
        "odata",
    ]
    for name in names:
        assert hasattr(fm, name), f"missing export: {name}"


def test_odata_namespace_usable():
    assert fm.odata.string("x") == "'x'"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_public_api.py -q`
Expected: FAIL — `AssertionError: missing export: FileMakerClient`.

- [ ] **Step 3: Update `src/filemaker_odata/__init__.py`**

```python
"""Python client for FileMaker's OData API."""

import logging

from filemaker_odata import odata
from filemaker_odata.client import FileMakerClient, OAuthUrl
from filemaker_odata.credentials import (
    BasicCredentials,
    Credentials,
    NullCredentials,
    OAuthCredentials,
    RawCredentials,
)
from filemaker_odata.errors import FileMakerError, RequestError
from filemaker_odata.filemaker import FileMaker, RecordsWithCount, ScriptResult
from filemaker_odata.operations.base import BatchOperationResponse
from filemaker_odata.request import Request, Response

# Keep the library silent unless the application configures logging.
logging.getLogger("filemaker_odata").addHandler(logging.NullHandler())

__all__ = [
    "FileMakerClient",
    "FileMaker",
    "RecordsWithCount",
    "ScriptResult",
    "OAuthUrl",
    "Credentials",
    "NullCredentials",
    "BasicCredentials",
    "OAuthCredentials",
    "RawCredentials",
    "Request",
    "Response",
    "RequestError",
    "FileMakerError",
    "BatchOperationResponse",
    "odata",
]
```

- [ ] **Step 4: Write `README.md`**

```markdown
# FileMaker OData (Python)

A sync Python client for FileMaker's OData v4 API. Managed with [uv](https://docs.astral.sh/uv/).

## Install

```bash
uv add filemaker-odata
```

## Usage

```python
from filemaker_odata import FileMakerClient, odata

client = FileMakerClient(server="demo.server.beezwax.net", database="test")
fm = client.with_basic_auth(username="my-user", password="my-pass")

# Read records with query options
records = fm.get_records(
    "Customers",
    select=["NAME", "COMPANY"],
    top=10,
    order_by=("NAME", "asc"),
)

# Safely interpolate user input into filters
records = fm.get_records("Customers", filter=f"NAME eq {odata.string(\"O'Brien\")}")

# Counts
total = fm.count_records("Customers")
page = fm.get_records_with_count("Customers", top=25)  # -> RecordsWithCount(data=..., count=...)

# Single record and container data
customer = fm.get_record("Customers", "1234")
photo_bytes = fm.get_value("Customers", "1234", "PHOTO")

# Run a script
result = fm.script("MyScript", {"foo": "bar"})  # -> ScriptResult(success=..., data=...)

# Transactional batch writes
results = (
    fm.batch()
    .create(table="Customers", record={"NAME": "New"})
    .update(table="Customers", record={"ID": "1234", "NAME": "Renamed"})
    .delete(table="Customers", id="9999")
    .execute()
)
```

## Authentication

`with_basic_auth`, `with_oauth`, and OAuth discovery via `client.get_oauth_url(...)`
and `client.get_auth_types()`.

## Logging

The library logs at DEBUG under the `filemaker_odata` logger and is silent by
default. Inject a custom `logging.Logger` via `FileMakerClient(..., logger=...)`.
```

- [ ] **Step 5: Run the entire suite**

Run: `uv run pytest -q`
Expected: PASS — all tests across `test_odata.py`, `test_credentials.py`, `test_request.py`, `test_operations.py`, `test_filemaker.py`, `test_client.py`, `test_public_api.py`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: expose public API and add README"
```

---

## Self-Review

**Spec coverage:**
- Package layout, uv tooling, Python 3.10+, httpx → Task 1. ✅
- `odata` helpers with exact messages → Task 2. ✅
- Error hierarchy (`FileMakerError`, `RequestError`) → Task 3. ✅
- Credentials (Protocol + Null/Basic/OAuth/Raw, base64) → Task 3. ✅
- `Request`/`Response`, `response_type` json/text/bytes, header merge, error data → Task 4. ✅
- Batch operations + fluent builder → Task 5. ✅
- `FileMaker`: url, metadata, get_records (+ all query options), get_records_with_count, count_records, get_record (ID encoding), get_value, subquery, crossjoin, script, batch; `RecordsWithCount`/`ScriptResult`; injectable stdlib logger → Task 6. ✅
- `FileMakerClient`: with_basic_auth/with_oauth, get_oauth_url (`OAuthUrl`), get_auth_types, url; `http_client` agent analogue → Task 7. ✅
- Public exports + README → Task 8. ✅
- `mergeDeep` and `FileMakerAuthenticator` intentionally omitted (decisions 5 & 6). ✅

**Placeholder scan:** No TBD/TODO, no vague "add error handling" steps — all code is concrete and runnable. f-strings avoid nested same-quote expressions so the tests run on Python 3.10+.

**Type consistency:** `RequestProtocol.get/post`, `MockRequest.get/post`, and `Request.get/post` share the same signature (`response_type` keyword, `Response` return). `FileMakerConfig.url`, `BatchOperationResponse(status, body)`, `RecordsWithCount(data, count)`, `ScriptResult(success, data)`, and `OAuthUrl(redirect_url, request_id)` are defined once and used consistently across tasks. Parameterize option order (`select, top, skip, filter, expand, orderby, count, format`) matches the URLs asserted in Task 6 tests.
