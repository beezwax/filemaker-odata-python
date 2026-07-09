# FileMaker OData (Python)

A sync Python client for FileMaker's OData v4 API. Managed with [uv](https://docs.astral.sh/uv/).

## Install

```bash
uv add filemaker-odata
```

## Usage

```python
from filemaker_odata import FileMakerClient, odata

client = FileMakerClient(server="demo.server.beezwax.net", database="test")
fm = client.with_basic_auth(username="my-user", password="my-pass")

# Read records with query options
records = fm.get_records(
    "Customers",
    select=["NAME", "COMPANY"],
    top=10,
    order_by=("NAME", "asc"),
)

# Safely interpolate user input into filters
literal = odata.string("O'Brien")
records = fm.get_records("Customers", filter=f"NAME eq {literal}")

# Counts
total = fm.count_records("Customers")
page = fm.get_records_with_count("Customers", top=25)  # -> RecordsWithCount(data=..., count=...)

# Single record and container data
customer = fm.get_record("Customers", "1234")
photo_bytes = fm.get_value("Customers", "1234", "PHOTO")

# Run a script
result = fm.script("MyScript", {"foo": "bar"})  # -> ScriptResult(success=..., data=...)

# Transactional batch writes
results = (
    fm.batch()
    .create(table="Customers", record={"NAME": "New"})
    .update(table="Customers", record={"ID": "1234", "NAME": "Renamed"})
    .delete(table="Customers", id="9999")
    .execute()
)
```

## Authentication

`with_basic_auth`, `with_oauth`, and OAuth discovery via `client.get_oauth_url(...)`
and `client.get_auth_types()`.

## Logging

The library logs at DEBUG under the `filemaker_odata` logger and is silent by
default. Inject a custom `logging.Logger` via `FileMakerClient(..., logger=...)`.
