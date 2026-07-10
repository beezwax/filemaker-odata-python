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
from filemaker_odata.operations.base import FileMakerConfig
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
        self._config = FileMakerConfig(server=server, database=database)
        self._http_client = http_client
        self._logger = logger

    def url(self, path: str) -> str:
        return self._config.url(path)

    def _make(self, credentials: Credentials) -> FileMaker:
        request = Request(credentials, client=self._http_client)
        return FileMaker(
            self._config.server, self._config.database, request, logger=self._logger
        )

    def with_basic_auth(self, *, username: str, password: str) -> FileMaker:
        return self._make(BasicCredentials(username=username, password=password))

    def with_oauth(self, *, request_id: str, identifier: str) -> FileMaker:
        return self._make(OAuthCredentials(request_id=request_id, identifier=identifier))

    def get_oauth_url(
        self, *, tracking_id: str, provider: str, return_url: Optional[str] = None
    ) -> OAuthUrl:
        request = Request(NullCredentials(), client=self._http_client)
        server = self._config.server
        url = (
            f"https://{server}/oauth/getoauthurl"
            f"?trackingID={tracking_id}&provider={provider}"
            f"&address={server}&X-FMS-OAuth-AuthType=2"
        )
        response = request.get(
            url,
            headers={
                "X-FMS-Application-Type": "9",
                "X-FMS-Application-Version": "15",
                "X-FMS-Return-URL": return_url or f"https://{server}/oauth-handler",
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
            f"https://{self._config.server}/fmws/oauthproviderinfo",
            headers={"Content-Type": "application/json"},
        )
        payload = response.data.get("data")
        if payload is not None:
            return [provider["Name"] for provider in payload["Provider"]]
        return ["basic"]
