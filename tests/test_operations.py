import pytest

from filemaker_odata.errors import FileMakerError
from filemaker_odata.operations.base import BatchOperationResponse, FileMakerConfig
from filemaker_odata.operations.builder import OperationBuilder
from filemaker_odata.operations.create import CreateOperation
from filemaker_odata.operations.delete import DeleteOperation
from filemaker_odata.operations.update import UpdateOperation

CONFIG = FileMakerConfig(server="demo.server.beezwax.net", database="test")


def test_config_builds_odata_url():
    assert CONFIG.url("FINDING") == (
        "https://demo.server.beezwax.net/fmi/odata/v4/test/FINDING"
    )


def test_create_request_body_contains_post_and_json():
    op = CreateOperation(config=CONFIG, table="FINDING", record={"FINDING": "body"})
    body = op.to_request_body(boundary="cs", change_id=1)
    assert "--cs\r\n" in body
    assert "Content-ID: 1\r\n" in body
    assert f"POST {CONFIG.url('FINDING')} HTTP/1.1\r\n" in body
    assert '{"FINDING": "body"}' in body


def test_create_parse_response_success():
    change = "\r\nHTTP/1.1 201 Created\r\n\r\n"
    assert op_create().parse_response(change) == BatchOperationResponse(status=201, body=None)


def test_create_parse_response_error_raises():
    change = 'HTTP/1.1 500 Error\r\n\r\n{"error":{"code":"1","message":"bad"}}'
    with pytest.raises(FileMakerError, match=r"\[CREATE OPERATION: FINDING\] bad"):
        op_create().parse_response(change)


def test_update_strips_id_and_targets_record():
    op = UpdateOperation(
        config=CONFIG, table="FINDING", record={"ID": "F-1", "FINDING": "x"}
    )
    body = op.to_request_body(boundary="cs", change_id=2)
    assert f"PATCH {CONFIG.url('FINDING')}('F-1') HTTP/1.1\r\n" in body
    assert '{"FINDING": "x"}' in body
    assert '"ID"' not in body


def test_update_parse_response_returns_json_body():
    change = 'HTTP/1.1 200 OK\r\n\r\n{"ID":"F-1","FINDING":"x"}'
    op = UpdateOperation(config=CONFIG, table="FINDING", record={"ID": "F-1"})
    assert op.parse_response(change) == BatchOperationResponse(
        status=200, body={"ID": "F-1", "FINDING": "x"}
    )


def test_delete_request_body_and_success():
    op = DeleteOperation(config=CONFIG, table="FINDING", id="F-1")
    body = op.to_request_body(boundary="cs", change_id=3)
    assert f"DELETE {CONFIG.url('FINDING')}('F-1') HTTP/1.1\r\n" in body
    change = "HTTP/1.1 204 No Content\r\n\r\n"
    assert op.parse_response(change) == BatchOperationResponse(status=204, body=None)


def test_builder_collects_operations_and_calls_back():
    seen = {}

    def callback(operations):
        seen["ops"] = operations
        return ["result"]

    result = (
        OperationBuilder(CONFIG, callback)
        .create(table="T", record={"a": 1})
        .update(table="T", record={"ID": "1"})
        .delete(table="T", id="1")
        .execute()
    )
    assert result == ["result"]
    assert [type(o).__name__ for o in seen["ops"]] == [
        "CreateOperation",
        "UpdateOperation",
        "DeleteOperation",
    ]


def op_create():
    return CreateOperation(config=CONFIG, table="FINDING", record={"FINDING": "body"})
