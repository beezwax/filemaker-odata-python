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
