"""PartMe Blender MCP public runtime identity.

Identity constants live in ``harness.version`` so that the Blender Add-on, which ships
the Harness under a different top-level ``__init__.py``, resolves the same values.
"""

from .harness.version import (  # noqa: F401
    MCP_SERVER_ID,
    PRODUCT_NAME,
    __version__,
)
