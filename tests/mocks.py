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
