import filemaker_odata as fm


def test_public_exports_present():
    names = [
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
    for name in names:
        assert hasattr(fm, name), f"missing export: {name}"


def test_odata_namespace_usable():
    assert fm.odata.string("x") == "'x'"
