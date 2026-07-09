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
