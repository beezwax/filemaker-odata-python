"""Helpers for safely building OData literals from untrusted input.

Each helper raises ``TypeError`` with a stable message on invalid input, so the
library behaves the same whether or not callers use type checking.
"""

import math
import re

_NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+|\d+\.\d+|\.\d+)$")
_INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9 _-]+$")


def _num_to_str(value: float) -> str:
    """Mirror JavaScript ``String(Number(...))``: integral floats lose the ``.0``."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return str(number)


def string(value) -> str:
    if not isinstance(value, str):
        raise TypeError("Invalid OData string")
    return "'" + value.replace("'", "''") + "'"


def number(value) -> str:
    if isinstance(value, bool):
        raise TypeError("Invalid OData number")
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise TypeError("Invalid OData number")
        return _num_to_str(value)
    if not isinstance(value, str):
        raise TypeError("Invalid OData number")
    normalized = value.strip()
    if not _NUMBER_PATTERN.match(normalized):
        raise TypeError("Invalid OData number")
    parsed = float(normalized)
    if not math.isfinite(parsed):
        raise TypeError("Invalid OData number")
    return _num_to_str(parsed)


def integer(value) -> str:
    if isinstance(value, bool):
        raise TypeError("Invalid OData integer")
    if not isinstance(value, (int, float, str)):
        raise TypeError("Invalid OData integer")
    normalized = _num_to_str(value) if isinstance(value, (int, float)) else value.strip()
    if not _INTEGER_PATTERN.match(normalized):
        raise TypeError("Invalid OData integer")
    return normalized


def boolean(value) -> str:
    if not isinstance(value, bool):
        raise TypeError("Invalid OData boolean")
    return "true" if value else "false"


def uuid(value) -> str:
    if not isinstance(value, str):
        raise TypeError("Invalid OData UUID")
    if not _UUID_PATTERN.match(value):
        raise TypeError("Invalid OData UUID")
    return string(value)


def identifier(value) -> str:
    if not isinstance(value, str):
        raise TypeError("Invalid OData identifier")
    if not _IDENTIFIER_PATTERN.match(value):
        raise TypeError("Invalid OData identifier")
    return '"' + value + '"'
