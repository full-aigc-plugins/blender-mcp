"""Single source of truth for product identity and version.

This module lives inside ``harness/`` on purpose: the Blender Add-on ships the Harness
under its own top-level package, whose ``__init__.py`` belongs to Blender's Add-on
loader rather than to the runtime. Keeping identity here means the version resolves in
both the pip-installed runtime and the installed Add-on.
"""

__version__ = "0.2.0"
VERSION_TUPLE = (0, 1, 1)
PRODUCT_NAME = "PartMe Blender MCP"
MCP_SERVER_ID = "partme_blender"
MCP_SERVER_NAME = "partme-blender-mcp"
MCP_PROTOCOL_VERSION = "2025-06-18"
HARNESS_PROTOCOL_VERSION = "codex-blender/v1"
BLENDER_DOWNLOAD_URL = "https://www.blender.org/download/"
