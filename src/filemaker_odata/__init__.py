"""Python client for FileMaker's OData API."""

import logging

# Keep the library silent unless the application configures logging.
logging.getLogger("filemaker_odata").addHandler(logging.NullHandler())
