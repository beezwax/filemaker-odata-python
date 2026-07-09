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
