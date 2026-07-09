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
