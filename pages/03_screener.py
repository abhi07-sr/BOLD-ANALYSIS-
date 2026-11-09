"""Root pages delegator for 03_screener."""

import importlib
import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

screener_module = importlib.import_module("src.dashboard.pages.03_screener")
if hasattr(screener_module, "render"):
    screener_module.render()

