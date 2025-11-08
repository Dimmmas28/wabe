def build_url(host: str, port: int, secure: bool = False) -> str:
    """Build a URL from host, port, and security flag."""
    scheme = "https" if secure else "http"
    return f"{scheme}://{host}:{port}"
