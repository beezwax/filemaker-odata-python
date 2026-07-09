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


def test_get_raises_request_error_on_invalid_json_body():
    def handler(request):
        return httpx.Response(200, text="not json")

    req = Request(NullCredentials(), client=_client(handler))
    with pytest.raises(RequestError):
        req.get("https://example.test/x")


def test_credential_headers_take_precedence_over_call_headers():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    req = Request(BasicCredentials(username="u", password="p"), client=_client(handler))
    req.get("https://example.test/x", headers={"Authorization": "Bearer override"})
    assert captured["auth"].startswith("Basic ")


def test_default_client_disables_timeout():
    req = Request(NullCredentials())
    assert req._client.timeout.connect is None
