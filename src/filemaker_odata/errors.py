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
