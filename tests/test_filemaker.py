import pytest

from filemaker_odata import odata
from filemaker_odata.errors import FileMakerError
from filemaker_odata.filemaker import FileMaker, RecordsWithCount, ScriptResult
from tests.mocks import MockRequest


def fixtures():
    request = MockRequest()
    fm = FileMaker(server="demo.server.beezwax.net", database="test", request=request)
    return fm, request


def test_url():
    fm, _ = fixtures()
    assert fm.url("foo") == "https://demo.server.beezwax.net/fmi/odata/v4/test/foo"


def test_metadata():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("$metadata"), data="someJSON")
    assert fm.metadata() == "someJSON"


def test_get_records_no_options():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$format=application/json"),
        data={"value": [{"ID": "1234", "NAME": "Fede", "COMPANY": "Beezwax"}]},
    )
    records = fm.get_records("people")
    assert len(records) == 1
    assert records[0]["NAME"] == "Fede"


def test_get_records_select_single():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$select="NAME"&$format=application/json'),
        data={"value": [{"NAME": "Fede"}]},
    )
    assert fm.get_records("people", select=["NAME"])[0]["NAME"] == "Fede"


def test_get_records_select_multiple():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$select="ID","NAME","COMPANY"&$format=application/json'),
        data={"value": [{"ID": "1234", "NAME": "Fede", "COMPANY": "Beezwax"}]},
    )
    assert fm.get_records("people", select=["ID", "NAME", "COMPANY"])[0]["ID"] == "1234"


def test_get_records_top_skip():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=5&$skip=10&$format=application/json"),
        data={"value": [{"ID": "11"}]},
    )
    assert fm.get_records("people", top=5, skip=10)[0]["ID"] == "11"


def test_get_records_filter_raw_and_escaped():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$filter=name eq 'O''Brien'&$format=application/json"),
        data={"value": [{"NAME": "O'Brien"}]},
    )
    literal = odata.string("O'Brien")  # -> 'O''Brien'
    records = fm.get_records("people", filter=f"name eq {literal}")
    assert records[0]["NAME"] == "O'Brien"


def test_get_records_expand():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$expand=orders&$format=application/json"),
        data={"value": [{"ID": "1234"}]},
    )
    assert len(fm.get_records("people", expand="orders")) == 1


def test_get_records_orderby_single():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$orderby="NAME" asc&$format=application/json'),
        data={"value": [{"NAME": "Alice"}, {"NAME": "Bob"}]},
    )
    assert fm.get_records("people", order_by=("NAME", "asc"))[0]["NAME"] == "Alice"


def test_get_records_orderby_multiple():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people?$orderby="COMPANY" asc,"NAME" desc&$format=application/json'),
        data={"value": [{"COMPANY": "Acme Corp", "NAME": "Zara"}]},
    )
    records = fm.get_records("people", order_by=[("COMPANY", "asc"), ("NAME", "desc")])
    assert records[0]["NAME"] == "Zara"


@pytest.mark.parametrize("flag,text", [(True, "true"), (False, "false")])
def test_get_records_count_flag(flag, text):
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url(f"people?$count={text}&$format=application/json"),
        data={"value": [{"ID": "1234"}]},
    )
    assert len(fm.get_records("people", count=flag)) == 1


def test_get_records_combined_options():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url(
            'people?$select="NAME","COMPANY"&$top=10&$skip=5'
            "&$filter=company eq 'Beezwax'&$orderby=\"NAME\" asc&$format=application/json"
        ),
        data={"value": [{"NAME": "Fede", "COMPANY": "Beezwax"}]},
    )
    records = fm.get_records(
        "people",
        select=["NAME", "COMPANY"],
        top=10,
        skip=5,
        filter="company eq 'Beezwax'",
        order_by=("NAME", "asc"),
    )
    assert records[0]["COMPANY"] == "Beezwax"


def test_get_records_metadata_false_appends_suffix():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$format=application/json;odata.metadata=none"),
        data={"value": []},
    )
    assert fm.get_records("people", metadata=False) == []


def test_get_records_with_count_reads_odata_count():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=1&$count=true&$format=application/json"),
        data={"@odata.count": 29, "value": [{"ID": "1234"}]},
    )
    result = fm.get_records_with_count("people", top=1)
    assert isinstance(result, RecordsWithCount)
    assert result.count == 29
    assert len(result.data) == 1


def test_get_records_with_count_reads_fm_count():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=1&$count=true&$format=application/json"),
        data={"@count": 29, "value": [{"ID": "1234"}]},
    )
    assert fm.get_records_with_count("people", top=1).count == 29


def test_get_records_with_count_defaults_zero():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=1&$count=true&$format=application/json"),
        data={"value": [{"ID": "1234"}]},
    )
    assert fm.get_records_with_count("people", top=1).count == 0


def test_get_records_with_count_null_odata_count_falls_back():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people?$top=1&$count=true&$format=application/json"),
        data={"@odata.count": None, "@count": 7, "value": [{"ID": "1"}]},
    )
    assert fm.get_records_with_count("people", top=1).count == 7


def test_count_records_endpoint_and_response_type():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("people/$count"), data="29")
    assert fm.count_records("people") == 29
    assert request.latest_request()["response_type"] == "text"


def test_count_records_with_filter():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people/$count?$filter=company eq 'Beezwax'"),
        data="12",
    )
    assert fm.count_records("people", filter="company eq 'Beezwax'") == 12


def test_count_records_trims_whitespace():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("people/$count"), data=" 29\n")
    assert fm.count_records("people") == 29


def test_count_records_rejects_non_numeric():
    fm, request = fixtures()
    request.mock(type="GET", url=fm.url("people/$count"), data="twenty-nine")
    with pytest.raises(FileMakerError, match=r'Invalid count response from "people/\$count": twenty-nine'):
        fm.count_records("people")


def test_get_record_by_id():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('1234')?$format=application/json"),
        data={"ID": "1234", "NAME": "Fede"},
    )
    assert fm.get_record("people", "1234")["NAME"] == "Fede"


def test_get_record_encodes_special_chars():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('test%40example.com')?$format=application/json"),
        data={"ID": "test@example.com"},
    )
    assert fm.get_record("people", "test@example.com")["ID"] == "test@example.com"


def test_get_value_returns_bytes():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('1234')/PHOTO/$value"),
        data=b"\x89PNG",
    )
    assert fm.get_value("people", "1234", "PHOTO") == b"\x89PNG"
    assert request.latest_request()["response_type"] == "bytes"


def test_subquery_returns_value_list():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("people('1234')/orders?$format=application/json"),
        data={"value": [{"ID": "o1"}]},
    )
    assert fm.subquery("people", "1234", "orders")[0]["ID"] == "o1"


def test_crossjoin_builds_url():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("$crossjoin(people,orders)?$format=application/json"),
        data={"value": []},
    )
    assert fm.crossjoin(tables=["people", "orders"]) == {"value": []}


def test_get_record_with_options():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url('people(\'1234\')?$select="NAME"&$expand=orders&$format=application/json'),
        data={"NAME": "Fede"},
    )
    assert fm.get_record("people", "1234", select=["NAME"], expand="orders")["NAME"] == "Fede"


def test_crossjoin_with_filter():
    fm, request = fixtures()
    request.mock(
        type="GET",
        url=fm.url("$crossjoin(people,orders)?$filter=people/ID eq orders/PID&$format=application/json"),
        data={"value": [{"x": 1}]},
    )
    result = fm.crossjoin(tables=["people", "orders"], filter="people/ID eq orders/PID")
    assert result["value"][0]["x"] == 1


def test_script_success():
    fm, request = fixtures()
    request.mock(
        type="POST",
        url=fm.url("Script.MyScript"),
        data={"scriptResult": {"code": 0, "resultParameter": {"ok": 1}}},
    )
    result = fm.script("MyScript", {"foo": "bar"})
    assert result == ScriptResult(success=True, data={"ok": 1})
    assert request.latest_request()["body"] == {"scriptParameterValue": {"foo": "bar"}}


def test_script_failure_returns_no_data():
    fm, request = fixtures()
    request.mock(
        type="POST",
        url=fm.url("Script.MyScript"),
        data={"scriptResult": {"code": 5, "resultParameter": {"ignored": 1}}},
    )
    result = fm.script("MyScript")
    assert result == ScriptResult(success=False, data=None)
    assert request.latest_request()["body"] is None


def test_batch_executes_and_parses_changeset():
    fm, request = fixtures()
    changeset_response = (
        "--batchresponse_1\r\n"
        "Content-Type: multipart/mixed; boundary=changesetresponse_1\r\n\r\n"
        "--changesetresponse_1\r\n"
        "Content-Type: application/http\r\n\r\n"
        'HTTP/1.1 200 OK\r\n\r\n{"ID":"F-1","FINDING":"updated"}\r\n'
        "--changesetresponse_1--\r\n"
        "--batchresponse_1--\r\n"
    )
    request.mock(type="POST", url=fm.url("$batch"), data=changeset_response)

    results = fm.batch().update(table="FINDING", record={"ID": "F-1", "FINDING": "updated"}).execute()

    assert len(results) == 1
    assert results[0].status == 200
    assert results[0].body == {"ID": "F-1", "FINDING": "updated"}
    assert request.latest_request()["headers"]["Content-Type"].startswith(
        "multipart/mixed; boundary=batch_"
    )
