# FileMaker API Reference

This document provides detailed documentation for all methods available on the
`FileMaker` class.

## Table of Contents

- [Configuration](#configuration)
- [Methods](#methods)
  - [url()](#url)
  - [metadata()](#metadata)
  - [get_records()](#get_records)
  - [get_records_with_count()](#get_records_with_count)
  - [count_records()](#count_records)
  - [get_record()](#get_record)
  - [get_value()](#get_value)
  - [subquery()](#subquery)
  - [crossjoin()](#crossjoin)
  - [batch()](#batch)
  - [script()](#script)
- [Query Options](#query-options)
- [OData Sanitization Utilities](#odata-sanitization-utilities)

## Configuration

The `FileMaker` class is constructed with:

```python
FileMaker(server: str, database: str, request: RequestProtocol, logger: logging.Logger | None = None)
```

- `server` — the FileMaker server host (e.g. `"demo.server.beezwax.net"`)
- `database` — the database name
- `request` — an object implementing the request protocol (normally a `Request`)
- `logger` — an optional `logging.Logger`; defaults to the silent `filemaker_odata` logger

**Note:** In most cases you'll use `FileMakerClient` to create authenticated
instances rather than constructing `FileMaker` directly. See the
[README](./README.md) for authentication examples.

```python
from filemaker_odata import FileMakerClient

client = FileMakerClient(server="demo.server.beezwax.net", database="test")
fm = client.with_basic_auth(username="my-user", password="my-pass")
```

Records are returned as plain `dict`s. Query options are passed as keyword
arguments (snake_case), not `$`-prefixed keys — see [Query Options](#query-options).

## Methods

### url()

Constructs a fully-qualified URL for FileMaker OData API endpoints.

**Signature:**

```python
def url(self, path: str) -> str
```

**Parameters:**

- `path` — The API path relative to the database endpoint

**Returns:** A complete HTTPS URL string

**Example:**

```python
endpoint = fm.url("MyTable")
# "https://demo.server.beezwax.net/fmi/odata/v4/test/MyTable"
```

---

### metadata()

Retrieves the OData metadata document for the database, which describes available
tables and their schemas.

**Signature:**

```python
def metadata(self) -> Any
```

**Returns:** The metadata document (typically XML text)

**Example:**

```python
metadata = fm.metadata()
print(metadata)
```

---

### get_records()

Retrieves records from a specified table with optional query options.

**Signature:**

```python
def get_records(
    self,
    table: str,
    *,
    select=None,
    top=None,
    skip=None,
    filter=None,
    expand=None,
    order_by=None,
    count=None,
    format=None,
    metadata=None,
) -> list[dict]
```

**Parameters:**

- `table` — The name of the table to query
- Query options as keyword arguments (see [Query Options](#query-options))

**Returns:** A list of records (dicts)

**Example:**

```python
# Get all records
all_records = fm.get_records("Customers")

# Get with filtering
filtered = fm.get_records("Customers", filter="Age gt 25", top=10)

# Get specific fields only
specific = fm.get_records("Customers", select=["NAME", "EMAIL", "PHONE"])

# Get with ordering
ordered = fm.get_records("Customers", order_by=("CREATED_DATE", "desc"), top=20)

# Get with multi-column ordering
multi_ordered = fm.get_records(
    "Customers",
    order_by=[("AGE", "desc"), ("NAME", "asc")],
    top=20,
)
```

---

### get_records_with_count()

Retrieves records along with the total count of matching records (ignoring
pagination). Supports both OData `@odata.count` and FileMaker `@count` response
fields.

**Signature:**

```python
def get_records_with_count(
    self,
    table: str,
    *,
    select=None,
    top=None,
    skip=None,
    filter=None,
    expand=None,
    order_by=None,
    format=None,
    metadata=None,
) -> RecordsWithCount
```

**Parameters:**

- `table` — The name of the table to query
- Query options as keyword arguments (see [Query Options](#query-options))

**Returns:** A `RecordsWithCount` dataclass with:

- `data` — list of records
- `count` — total number of matching records

**Example:**

```python
result = fm.get_records_with_count("Products", filter="Price gt 100", top=10, skip=0)

print(f"Showing {len(result.data)} of {result.count} products")
# Showing 10 of 245 products
```

---

### count_records()

Retrieves only the total count of matching records from the direct OData
`/{table}/$count` endpoint.

**Signature:**

```python
def count_records(self, table: str, *, filter=None) -> int
```

**Parameters:**

- `table` — The name of the table to count
- `filter` — Optional OData filter expression

**Returns:** The count as an `int`

**Raises:** `FileMakerError` if the server response is not a valid integer count

**Example:**

```python
# Count all records
total_products = fm.count_records("Products")

# Count matching records
expensive = fm.count_records("Products", filter="Price gt 100")

print(f"Found {expensive} expensive products")
```

---

### get_record()

Retrieves a single record by its ID.

**Signature:**

```python
def get_record(
    self,
    table: str,
    id: str,
    *,
    select=None,
    expand=None,
    format=None,
    metadata=None,
) -> dict
```

**Parameters:**

- `table` — The name of the table
- `id` — The record ID (primary key value)
- Query options as keyword arguments (supports `select`, `expand`, `format`, `metadata`)

**Returns:** A single record dict

**Example:**

```python
# Get a single record
customer = fm.get_record("Customers", "CUST-12345")
print(customer["NAME"])

# Get specific fields only
customer_basic = fm.get_record("Customers", "CUST-12345", select=["NAME", "EMAIL"])

# Get record with expanded relationships
customer_with_orders = fm.get_record("Customers", "CUST-12345", expand="Orders")

# IDs with special characters are automatically URL-encoded
user = fm.get_record("Users", "user@example.com")
# Internally encoded as: Users('user%40example.com')
```

---

### get_value()

Retrieves the raw value of a specific field from a record. Useful for binary data
like container fields.

**Signature:**

```python
def get_value(self, table: str, id: str, field: str) -> bytes
```

**Parameters:**

- `table` — The name of the table
- `id` — The record ID
- `field` — The field name to retrieve

**Returns:** The raw field value as `bytes`

**Example:**

```python
# Get a container field (image, PDF, etc.)
image_data = fm.get_value("Products", "PROD-001", "ProductImage")

# Write it to a file
with open("product.jpg", "wb") as f:
    f.write(image_data)
```

---

### subquery()

Retrieves related records through a relationship/portal.

**Signature:**

```python
def subquery(
    self,
    table: str,
    record_id: str,
    path: str,
    *,
    select=None,
    top=None,
    skip=None,
    filter=None,
    expand=None,
    order_by=None,
    count=None,
    format=None,
    metadata=None,
) -> list[dict]
```

**Parameters:**

- `table` — The parent table name
- `record_id` — The parent record ID
- `path` — The relationship/portal name
- Query options as keyword arguments

**Returns:** A list of related records (dicts)

**Example:**

```python
# Get all orders for a specific customer
orders = fm.subquery("Customers", "CUST-12345", "Orders")

# Get with filtering and limiting
recent_orders = fm.subquery(
    "Customers",
    "CUST-12345",
    "Orders",
    filter="OrderDate gt 2024-01-01",
    top=5,
    order_by=("ORDER_DATE", "desc"),
)
```

---

### crossjoin()

Performs a cross-join query across multiple tables.

**Signature:**

```python
def crossjoin(
    self,
    *,
    tables: Sequence[str],
    filter=None,
    expand=None,
    format=None,
    metadata=None,
) -> Any
```

**Parameters:**

- `tables` — List of table names to join
- Query options as keyword arguments (supports `filter`, `expand`, `format`, `metadata`)

**Returns:** Response data (parsed JSON, or XML text depending on `format`)

**Example:**

```python
# JSON format (default)
result = fm.crossjoin(
    tables=["Customers", "Orders"],
    filter="Customers/ID eq Orders/CustomerID",
    expand="Customers,Orders",
)

# XML format
xml_result = fm.crossjoin(
    tables=["Customers", "Orders"],
    filter="Customers/ID eq Orders/CustomerID",
    expand="Customers,Orders",
    format="xml",
)
```

---

### batch()

Creates a batch operation builder for executing multiple create, update, and
delete operations transactionally. All operations succeed together or all fail.

**Signature:**

```python
def batch(self) -> OperationBuilder
```

**Returns:** An `OperationBuilder` instance for chaining operations

**Available Operations:**

- `.create(table=..., record=...)` — Create a new record
- `.update(table=..., record=...)` — Update an existing record (must include `ID`)
- `.delete(table=..., id=...)` — Delete a record
- `.execute()` — Send the batch; returns a list of `BatchOperationResponse`

Each `BatchOperationResponse` has `status` (int) and `body` (the parsed response
body, or `None` for create/delete).

**Example:**

```python
# Execute multiple operations in a transaction
results = (
    fm.batch()
    .create(table="Customers", record={"NAME": "John Doe", "EMAIL": "john@example.com"})
    .update(table="Orders", record={"ID": "ORDER-123", "STATUS": "Shipped"})
    .delete(table="Products", id="PROD-999")
    .execute()
)

# results is a list with one response per operation
print(results[0])  # Create result
print(results[1])  # Update result
print(results[2])  # Delete result
```

**Transaction Behavior:**

```python
from filemaker_odata import FileMakerError

# If any operation fails, ALL operations are rolled back
try:
    results = (
        fm.batch()
        .create(table="Customers", record={"NAME": "Jane"})
        .delete(table="Orders", id="INVALID-ID")  # This fails
        .execute()
    )
except FileMakerError:
    # The customer creation is also rolled back
    print("Transaction failed, no changes were made")
```

---

### script()

Executes a FileMaker script and returns the result.

**Signature:**

```python
def script(self, name: str, params: dict | None = None) -> ScriptResult
```

**Parameters:**

- `name` — The name of the FileMaker script to execute
- `params` — Optional parameters to pass to the script

**Returns:** A `ScriptResult` dataclass with:

- `success` — `True` if the script returned code 0, `False` otherwise
- `data` — The script's result parameter (only present if successful, else `None`)

**Example:**

```python
# Run a script without parameters
result = fm.script("CalculateTotals")
if result.success:
    print("Script completed successfully")

# Run a script with parameters
email_result = fm.script(
    "SendEmail",
    {"recipient": "customer@example.com", "subject": "Order Confirmation", "orderId": "ORDER-123"},
)

if email_result.success:
    print(f"Sent {email_result.data['SENT']} emails")
else:
    print("Failed to send email")

# Script with complex return data
validation = fm.script("ValidateOrder", {"orderId": "ORDER-456"})

if validation.success and validation.data:
    if validation.data["VALID"]:
        print("Order is valid")
    else:
        print("Validation errors:", validation.data["ERRORS"])
```

---

## Query Options

Most query methods accept the following keyword arguments for filtering, sorting,
and pagination:

| Option | Type | Description |
|--------|------|-------------|
| `select` | `list[str]` | Select specific fields |
| `top` | `int` | Limit number of results |
| `skip` | `int` | Skip first N results (pagination) |
| `filter` | `str` | OData filter expression |
| `expand` | `str` | Expand related records |
| `order_by` | `tuple[str, str]` or `list[tuple[str, str]]` | Sort by one or multiple columns; each tuple is `(field, "asc" \| "desc")` |
| `count` | `bool` | Include total count |
| `format` | `"json"` or `"xml"` | Response format (default: `json`) |
| `metadata` | `bool` | Include OData metadata (default: `True`) |

Not every method accepts every option — `get_record` supports `select`, `expand`,
`format`, `metadata`; `count_records` supports only `filter`; `crossjoin` supports
`filter`, `expand`, `format`, `metadata`.

### select

Select specific fields to return (reduces payload size).

```python
records = fm.get_records("Customers", select=["ID", "NAME", "EMAIL"])
# Fields are quoted in the URL: $select="ID","NAME","EMAIL"
```

### top

Limit the number of records returned.

```python
records = fm.get_records("Products", top=20)
```

### skip

Skip a number of records (useful for pagination).

```python
# Get page 3 (records 41-60)
records = fm.get_records("Products", skip=40, top=20)
```

### filter

Filter records using OData filter syntax. See
[FileMaker's OData documentation](https://help.claris.com/en/odata-guide/content/query-option-filter.html)
for complete filter syntax. When interpolating user input, use the
[OData helpers](#odata-sanitization-utilities).

```python
# Comparison operators
adults = fm.get_records("Users", filter="Age ge 18")

# String functions
gmail_users = fm.get_records("Users", filter="contains(Email, 'gmail.com')")

# Logical operators
active_customers = fm.get_records(
    "Customers", filter="Status eq 'Active' and TotalPurchases gt 1000"
)

# Date comparisons
recent_orders = fm.get_records("Orders", filter="OrderDate gt 2024-01-01")
```

### expand

Include related records in the response.

```python
customers = fm.get_records("Customers", expand="ORDERS")
```

### order_by

Sort results by one or multiple fields in ascending or descending order.

```python
# Sort by single column
products = fm.get_records("Products", order_by=("PRICE", "desc"))

# Sort by multiple columns
orders = fm.get_records(
    "Orders",
    order_by=[("STATUS", "asc"), ("ORDER_DATE", "desc")],
)
# Sorted by STATUS ascending, then ORDER_DATE descending within each status
```

### count

Include the total count of matching records in collection responses
(automatically enabled in `get_records_with_count`). Use `count_records()` when
you only need the count from the direct `/{table}/$count` endpoint.

```python
records = fm.get_records("Products", count=True, top=10)
```

### format

Control the response format (JSON or XML).

```python
# JSON format (default)
json_records = fm.get_records("Products", format="json")

# XML format
xml_records = fm.get_records("Products", format="xml")
```

### metadata

Control whether OData metadata is included in the response. When set to `False`,
adds `;odata.metadata=none` to the format parameter, reducing response payload
size.

```python
# Include metadata (default)
with_metadata = fm.get_records("Products", metadata=True)
# Response includes @odata.context and other metadata fields

# Exclude metadata for a smaller payload
without_metadata = fm.get_records("Products", metadata=False)
# Response contains only the raw data
```

### Combining Options

All applicable query options can be combined for complex queries.

```python
result = fm.get_records_with_count(
    "Products",
    select=["ID", "NAME", "PRICE", "CATEGORY"],
    filter="Price gt 50 and Category eq 'Electronics'",
    order_by=("PRICE", "desc"),
    top=20,
    skip=0,
)

print(f"Found {result.count} products")
print(f"Showing {len(result.data)} results")
```

---

## OData Sanitization Utilities

The package exports an `odata` helper module for constructing OData literals and
validating identifiers when building query strings.

```python
from filemaker_odata import odata
```

### odata.string()

Creates an OData string literal. Single quotes are escaped by doubling them. This
helper does not URL encode.

```python
odata.string("O'Brien")  # "'O''Brien'"
```

### odata.number()

Validates a finite number or numeric string and returns the normalized OData
literal.

```python
odata.number(42)       # "42"
odata.number(" -12.5 ")  # "-12.5"
```

### odata.integer()

Validates an integer number or integer string.

```python
odata.integer("42")  # "42"
```

### odata.boolean()

Returns an OData boolean literal.

```python
odata.boolean(True)  # "true"
```

### odata.uuid()

Validates a UUID and returns it as an OData string literal.

```python
odata.uuid("280dc895-23f6-4368-be3b-3ea81d360f62")
# "'280dc895-23f6-4368-be3b-3ea81d360f62'"
```

### odata.identifier()

Validates and quotes a simple FileMaker field or table identifier. Use this for
trusted metadata or allow-listed identifiers, not arbitrary user text.

```python
odata.identifier("Customer Name")  # '"Customer Name"'
```

### Safe Filter Interpolation

```python
records = fm.get_records(
    "Customers",
    filter=f"{odata.identifier('NAME')} eq {odata.string(user_input)}",
)
```

Raw `filter` strings remain fully supported. The helpers reduce OData literal and
identifier injection risk, but they do not sanitize a complete arbitrary OData
expression. Each helper raises `TypeError` on invalid input.
