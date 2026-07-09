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
