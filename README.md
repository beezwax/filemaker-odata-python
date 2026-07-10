# FileMaker OData (Python)

A sync Python client for FileMaker's OData v4 API. Managed with [uv](https://docs.astral.sh/uv/).

## Install

Installed straight from GitHub (not published to PyPI):

```bash
uv add "git+https://github.com/beezwax/filemaker-odata-python"
```

Pin to a branch, tag, or commit for reproducible builds:

```bash
uv add "git+https://github.com/beezwax/filemaker-odata-python@main"
uv add "git+https://github.com/beezwax/filemaker-odata-python@v0.0.1"
```

For a private repo, use the SSH form so uv uses your git credentials:

```bash
uv add "git+ssh://git@github.com/beezwax/filemaker-odata-python"
```

The distribution name is `filemaker-odata`; the import name is `filemaker_odata`.

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

### Basic Authentication

```python
from filemaker_odata import FileMakerClient

client = FileMakerClient(server="demo.server.beezwax.net", database="test")
fm = client.with_basic_auth(username="my-user", password="my-pass")

# Now use the fm instance to make requests
records = fm.get_records("MY_TABLE")
```

### OAuth Authentication

OAuth is a multi-step flow: get a redirect URL, send the user to it, then exchange
the identifier from the callback for an authenticated client.

```python
client = FileMakerClient(server="demo.server.beezwax.net", database="test")

# Step 1: Get the OAuth redirect URL
result = client.get_oauth_url(
    tracking_id="unique-tracking-id",  # Anything; passed back in the redirect
    provider="Google",                 # Whichever provider FileMaker is configured for
    # If your app runs on a different host than FileMaker, see "OAuth handler" below
    return_url="https://demo.server.beezwax.net/my-web-app/oauth-callback",
)
# result -> OAuthUrl(redirect_url=..., request_id=...)

# Step 2: Persist result.request_id (e.g. in the user's session)
session["request_id"] = result.request_id

# Step 3: Redirect the user to result.redirect_url
#         The user authenticates with the OAuth provider...

# Step 4: In your OAuth callback route, read the identifier from the query string
identifier = request.args["identifier"]   # from the OAuth redirect
request_id = session["request_id"]

# Step 5: Create an authenticated FileMaker instance
fm = client.with_oauth(request_id=request_id, identifier=identifier)

records = fm.get_records("MY_TABLE")
```

### Available authentication types

To branch on which providers a server supports, use `get_auth_types()`:

```python
types = client.get_auth_types()   # e.g. ["basic", "Google"]
```

### OAuth handler (cross-host redirects)

When FileMaker and your web app are on different hosts, FileMaker won't redirect
back to your app during the OAuth step. The `oauth-handler` proxy (a small
redirector that sits on the FileMaker server) works around this: the flow becomes
`web → FileMaker → FileMaker oauth-handler → web`.

The handler redirects to whatever URL you put in `tracking_id`, so instead of a
cross-host `return_url` (which won't work):

```python
result = client.get_oauth_url(
    tracking_id="unique-tracking-id",
    provider="MyProvider",
    return_url="https://my-web-app.com/sessions/oauth",  # Won't work: different hosts
)
```

point `return_url` at the handler and put your app's callback in `tracking_id`:

```python
result = client.get_oauth_url(
    tracking_id="https://my-web-app.com/sessions/oauth",       # handler redirects here
    provider="MyProvider",
    return_url="https://my.filemaker.server.com/oauth-handler",  # back to the handler first
)
```

This also lets you run the flow against `localhost` during development. See the
`oauth-handler` repository for setup instructions.

### Self-signed certificates / custom HTTP client

Some FileMaker servers use self-signed certificates. Pass a configured
`httpx.Client` as `http_client` to control TLS verification, proxies, or timeouts
(this is the analogue of the TS `agent` option):

```python
import httpx
from filemaker_odata import FileMakerClient

client = FileMakerClient(
    server="demo.server.beezwax.net",
    database="example",
    http_client=httpx.Client(verify=False),  # trust a self-signed cert
)
```

## API Reference

Full method documentation is in [API.md](./API.md).

## Logging

The library logs at DEBUG under the `filemaker_odata` logger and is silent by
default. Inject a custom `logging.Logger` via `FileMakerClient(..., logger=...)`.

## Development

This project uses [uv](https://docs.astral.sh/uv/). `uv run` syncs the
environment (Python + dependencies from `uv.lock`) before running, so no
separate install step is needed.

```bash
uv sync                 # create the venv and install deps (optional; uv run does this)
uv run pytest           # run the full test suite
uv run pytest -q        # quiet output
uv run pytest tests/test_filemaker.py -v   # run one file, verbose
```
