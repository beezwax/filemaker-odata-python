import pytest

from filemaker_odata import odata


class TestString:
    def test_wraps_values_in_single_quotes(self):
        assert odata.string("Beezwax") == "'Beezwax'"

    def test_escapes_single_quotes_by_doubling(self):
        assert odata.string("O'Brien") == "'O''Brien'"

    def test_does_not_url_encode_the_literal(self):
        assert odata.string("A B&C") == "'A B&C'"

    def test_rejects_non_string_values(self):
        with pytest.raises(TypeError, match="Invalid OData string"):
            odata.string(True)


class TestNumber:
    def test_accepts_finite_numbers(self):
        assert odata.number(42) == "42"
        assert odata.number(-12.5) == "-12.5"

    def test_accepts_numeric_strings(self):
        assert odata.number("42") == "42"
        assert odata.number("  -12.5  ") == "-12.5"

    def test_canonicalizes_non_standard_string_forms(self):
        assert odata.number("+42") == "42"
        assert odata.number("01") == "1"
        assert odata.number(".5") == "0.5"

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), "", "12abc", True, None, {}])
    def test_rejects_invalid_numbers(self, value):
        with pytest.raises(TypeError, match="Invalid OData number"):
            odata.number(value)

    def test_preserves_large_integer_precision(self):
        assert odata.number(9007199254740993) == "9007199254740993"
        assert odata.number("9007199254740993") == "9007199254740993"


class TestInteger:
    def test_accepts_integers(self):
        assert odata.integer(42) == "42"
        assert odata.integer(" -12 ") == "-12"

    @pytest.mark.parametrize("value", [12.5, "12.5", True, None, {}])
    def test_rejects_non_integers(self, value):
        with pytest.raises(TypeError, match="Invalid OData integer"):
            odata.integer(value)

    def test_preserves_large_integer_precision(self):
        assert odata.integer(9007199254740993) == "9007199254740993"


class TestBoolean:
    def test_accepts_booleans(self):
        assert odata.boolean(True) == "true"
        assert odata.boolean(False) == "false"

    def test_rejects_non_boolean_values(self):
        with pytest.raises(TypeError, match="Invalid OData boolean"):
            odata.boolean("true")


class TestUuid:
    def test_accepts_valid_uuid(self):
        assert odata.uuid("280dc895-23f6-4368-be3b-3ea81d360f62") == (
            "'280dc895-23f6-4368-be3b-3ea81d360f62'"
        )

    def test_accepts_uuidv7(self):
        assert odata.uuid("0196f682-e18d-7000-8000-000000000000") == (
            "'0196f682-e18d-7000-8000-000000000000'"
        )

    @pytest.mark.parametrize(
        "value",
        ["not-a-uuid", "0196f682-e18d-7000-7000-000000000000", True],
    )
    def test_rejects_bad_uuids(self, value):
        with pytest.raises(TypeError, match="Invalid OData UUID"):
            odata.uuid(value)


class TestIdentifier:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("NAME", '"NAME"'),
            ("Customer Name", '"Customer Name"'),
            ("customer_id", '"customer_id"'),
            ("Order-Number", '"Order-Number"'),
        ],
    )
    def test_quotes_safe_identifiers(self, value, expected):
        assert odata.identifier(value) == expected

    @pytest.mark.parametrize(
        "value", ['NA"ME', "Orders/ID", "NAME)&$top=1", "", True, 123]
    )
    def test_rejects_unsafe_identifiers(self, value):
        with pytest.raises(TypeError, match="Invalid OData identifier"):
            odata.identifier(value)
