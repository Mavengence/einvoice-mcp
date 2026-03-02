"""MCP server for German e-invoice compliance (XRechnung/ZUGFeRD)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("einvoice-mcp")
except PackageNotFoundError:
    __version__ = "0.1.0"
