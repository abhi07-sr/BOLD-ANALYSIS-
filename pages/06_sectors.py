"""Root pages delegator for 06_sectors."""

import importlib
import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

sectors_module = importlib.import_module("src.dashboard.pages.06_sectors")
if hasattr(sectors_module, "render"):
    sectors_module.render()

