class SchemaUnavailableError(RuntimeError):
    """Raised when a schema-backed feature is requested without valid schemas."""
