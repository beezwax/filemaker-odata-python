# FileMaker OData — Python Port Design

**Date:** 2026-07-09
**Status:** Approved

## Summary

A Python port of the TypeScript/JavaScript `filemaker-odata` library, which is a
client for FileMaker's OData v4 API. The port preserves the library's structure
and full feature set while adopting idiomatic Python conventions.

Source of truth for behavior: the existing TS library at
`/Users/gosukiwi/Beezwax/filemaker-odata` (`src/` and `tests/`).

## Key decisions

1. **Sync-only.** Uses `httpx.Client` (blocking). No async API. FileMaker OData
   clients are typically used in scripts, ETL, and request handlers where sync is
   the least-friction choice and easiest to test. (Async could be added later via
   a parallel `AsyncFileMaker` sharing the URL/parameterize logic, but is out of
   scope.)
2. **Pythonic naming (snake_case).** `get_records`, `count_records`,
   `with_basic_auth`, `get_oauth_url`, `order_by`, etc. Not a 1:1 name port of the
   TS API.
3. **Query options as keyword arguments (snake_case).** Since Python cannot use
   `$`-prefixed kwargs, OData query options are passed as keyword args and mapped
   to their `$`-prefixed OData form internally.
4. **stdlib `logging`, injectable.** Replaces the custom `ILogger`/`Logger`/
   `NullLogger`. `FileMaker` accepts an optional `logging.Logger`; a custom logger
   can be injected. Defaults to a `filemaker_odata` logger with a `NullHandler`
   (silent unless the app configures logging).
5. **Drop `mergeDeep`.** httpx merges request/client headers natively, so the TS
   `mergeDeep` helper and its tests are not ported.
6. **uv for tooling.** `uv` manages the Python toolchain and dependencies.

## Tooling & dependencies

- **Python 3.10+** (uses `X | Y` unions, `match` where helpful, modern typing).
- **uv** manages Python (`.python-version`) and deps. `uv run pytest` runs tests.
- Runtime dependency: **httpx**.
- Dev dependency: **pytest**.
- Packaged as `filemaker_odata` under `src/` layout with `pyproject.toml`.

## Package layout

```
filemaker-odata-python/
  pyproject.toml
  .python-version
  README.md
  src/filemaker_odata/
    __init__.py           # public exports
    client.py             # FileMakerClient (facade + OAuth URL / auth-types)
    filemaker.py          # FileMaker (core API)
    credentials.py        # Credentials protocol + Basic/OAuth/Raw/Null
    request.py            # Request (httpx), RequestError, Response
    odata.py              # escaping helpers
    authenticator.py      # deprecated FileMakerAuthenticator (Data API sessions)
    operations/
      __init__.py
      base.py             # BatchOperation protocol, BatchOperationResponse
      builder.py          # OperationBuilder (fluent)
      create.py
      update.py
      delete.py
  tests/
    conftest.py
    mocks.py              # MockRequest implementing the request protocol
    test_filemaker.py
    test_odata.py
```

## Components

### `request.py` — HTTP layer

- **`Response`** dataclass: `data` (parsed body — `dict`/`list`, `str`, or `bytes`
  depending on `response_type`) and `headers` (mapping).
- **`RequestError(FileMakerError)`**: raised on any HTTP/transport failure; carries
  `.data` (the response body when available, else `None`). Replaces the TS
  `RequestError` + `isRequestError` guard — callers use `except RequestError`.
- **`Request`**: wraps an `httpx.Client`. Constructed with a `Credentials` and an
  optional httpx client/transport (the Python analogue of the TS `agent` — used
  for custom TLS/proxy config in tests and advanced setups).
  - `get(url, *, headers=None, response_type="json") -> Response`
  - `post(url, body, *, headers=None, response_type="json") -> Response`
  - `response_type` controls body parsing: `"json"` → parsed JSON, `"text"` →
    `str`, `"bytes"` → raw `bytes`. (Replaces axios `responseType`.)
  - Merges credential `authorization_headers` with per-call headers (httpx-native).

### `credentials.py`

- **`Credentials`** Protocol: read-only `authorization_headers -> dict[str, str]`.
- **`NullCredentials`** — empty headers.
- **`BasicCredentials(username, password)`** — `Authorization: Basic <b64>` via
  stdlib `base64` (replaces `btoa`).
- **`OAuthCredentials(request_id, identifier)`** — OData version + FM OAuth headers.
- **`RawCredentials(authorization)`** — passes a raw `Authorization` header value.

### `filemaker.py` — `FileMaker`

Constructor: `FileMaker(server, database, request, logger=None)`.
`logger` defaults to `logging.getLogger("filemaker_odata")` (NullHandler).

Methods (records are plain `dict`; sequences are `list[dict]`):

- `url(path) -> str` — `https://{server}/fmi/odata/v4/{database}/{path}`
- `metadata() -> Any`
- `get_records(table, *, select=None, top=None, skip=None, filter=None,
  expand=None, order_by=None, count=None, format=None, metadata=None) -> list[dict]`
- `get_records_with_count(table, **query) -> RecordsWithCount` — forces
  `count=True`; reads `@odata.count` then `@count`, defaults to `0`.
- `count_records(table, *, filter=None) -> int` — hits `{table}/$count`, parses a
  plain-text integer, validates it is a non-negative integer string (raises
  `ValueError`/`FileMakerError` on invalid response).
- `get_record(table, id, *, select=None, expand=None, format=None,
  metadata=None) -> dict` — URL-encodes `id`.
- `get_value(table, id, field) -> bytes` — `response_type="bytes"`.
- `subquery(table, record_id, path, *, select=None, top=None, skip=None,
  filter=None, expand=None, order_by=None, count=None, format=None,
  metadata=None) -> list[dict]`
- `crossjoin(*, tables, filter=None, expand=None, format=None, metadata=None) -> Any`
- `script(name, params=None) -> ScriptResult` — POSTs
  `{"scriptParameterValue": params}` when params given; `success` is
  `scriptResult.code == 0`; `data` is `resultParameter` on success else `None`.
- `batch() -> OperationBuilder`

Result shapes (dataclasses, replacing TS inline objects):

- `RecordsWithCount(data: list[dict], count: int)`
- `ScriptResult(success: bool, data: Any | None)`

Query-option mapping (mirrors TS `parameterize`):

- No options → `$format=application/json`.
- `select=[...]` → `$select="A","B"` (each field double-quoted; embedded `"`
  doubled).
- `top`/`skip` → `$top`/`$skip`.
- `filter` → `$filter=<raw>` (raw OData string; callers escape via `odata.*`).
- `expand` → `$expand`.
- `order_by` → accepts a single `(field, "asc"|"desc")` tuple or a list of them →
  `$orderby="F" asc,"G" desc`.
- `count` (bool) → `$count=true|false`.
- `format` (`"json"`|`"xml"`) + `metadata` (bool, default `True`) →
  `$format=application/json` / `application/xml`, with `;odata.metadata=none`
  appended when `metadata=False`.
- Count parameterization: only `$filter` is emitted (or empty).

`get_record` ID encoding matches the TS test (`test@example.com` →
`test%40example.com`).

### `client.py` — `FileMakerClient`

Constructor: `FileMakerClient(server, database, *, http_client=None, logger=None)`
(`http_client` is the httpx `agent` analogue).

- `with_basic_auth(username, password) -> FileMaker`
- `with_oauth(request_id, identifier) -> FileMaker`
- `get_oauth_url(tracking_id, provider, return_url=None) -> OAuthUrl` — dataclass
  `OAuthUrl(redirect_url, request_id)`; reads the `x-fms-request-id` response
  header; raises if absent.
- `get_auth_types() -> list[str]` — returns provider names, or `["basic"]`.
- `url(path) -> str`

### `operations/` — batch

- **`base.py`**: `BatchOperation` Protocol (`to_request_body(boundary, change_id)
  -> str`, `parse_response(change) -> BatchOperationResponse`);
  `BatchOperationResponse(status: int, body: Any)`.
- **`builder.py`**: `OperationBuilder` with fluent `update(table, record)`,
  `create(table, record)`, `delete(table, id)` (each returns `self`) and
  `execute() -> list[BatchOperationResponse]`.
- **`create.py` / `update.py` / `delete.py`**: build the multipart change parts
  (POST / PATCH / DELETE), parse per-operation HTTP status, raise `FileMakerError`
  on status `>= 300` with the FileMaker error message. `update` strips `ID` from
  the PATCH body and targets `{table}('{ID}')`.
- Batch execution builds `batch_<uuid>` / `changeset_<uuid>` boundaries (via
  `uuid.uuid4()`), POSTs `multipart/mixed`, splits the response on the returned
  changeset boundary, and maps each change to its operation's `parse_response`.
- Byte length for `Content-Length` uses `len(json.encode("utf-8"))`.

### `authenticator.py` — deprecated

Port of `FileMakerAuthenticator` (FileMaker Data API sessions, not OData), marked
deprecated (docstring + `warnings.warn(DeprecationWarning)`), kept for parity:
`get_auth_type`, `get_oauth_url`, `get_token_using_oauth`,
`get_token_using_credentials`. Uses the Data API base URL
`https://{server}/fmi/data/vLatest/databases/{database}/`.

### `odata.py` — escaping helpers

Module-level functions mirroring the TS `odata` object, each raising `TypeError`
with the exact TS message on invalid input:

- `string(value) -> str` — wraps in single quotes, doubles embedded `'`.
- `number(value) -> str` — accepts finite numbers / numeric strings; canonicalizes
  (`"+42"`→`"42"`, `"01"`→`"1"`, `".5"`→`"0.5"`); rejects NaN/inf/invalid.
- `integer(value) -> str` — accepts int / integer strings (trimmed); rejects
  decimals.
- `boolean(value) -> str` — `"true"`/`"false"`; rejects non-bool.
- `uuid(value) -> str` — validates RFC 4122 variant pattern (incl. v7); returns a
  quoted string literal.
- `identifier(value) -> str` — validates `^[A-Za-z0-9 _-]+$`; returns a
  double-quoted identifier.

Exposed both as individual functions and grouped access (e.g. an `odata`
namespace/module) so callers can write `odata.string(...)`.

### `__init__.py` — public exports

Exports `FileMakerClient`, `FileMaker`, credentials classes, `Request`,
`RequestError`, `FileMakerError`, the `odata` helpers, `FileMakerAuthenticator`,
and the result dataclasses (`RecordsWithCount`, `ScriptResult`, `OAuthUrl`,
`BatchOperationResponse`).

## Error handling

- `FileMakerError(Exception)` — base.
- `RequestError(FileMakerError)` — transport/HTTP failures; carries `.data`.
- Batch operations and `count_records` raise `FileMakerError` on invalid/failed
  responses with descriptive messages matching the TS behavior.

## Testing

pytest suite mirroring `tests/filemaker.test.ts`:

- **`mocks.py`**: `MockRequest` implementing the request protocol (register
  GET/POST responses by URL; record the latest request for assertions) — same
  approach as the TS `MockRequest`.
- **`test_filemaker.py`**: URL construction; `metadata`; `get_records` with each
  option and combined options; `get_records_with_count` (`@odata.count`,
  `@count`, default `0`); `count_records` (endpoint, filter, whitespace-trimmed
  parse, non-numeric rejection); `get_record` (fetch + special-char ID encoding).
- **`test_odata.py`**: full parity with the TS `odata helpers` describe block
  (string/number/integer/boolean/uuid/identifier, including all rejection cases).
- `mergeDeep` tests are **not** ported (helper removed).

## Out of scope

- Async API (`AsyncFileMaker`).
- A `find` batch operation (the TS code notes this is intentionally unimplemented).
- Publishing to PyPI / packaging distribution config beyond a working
  `pyproject.toml`.
