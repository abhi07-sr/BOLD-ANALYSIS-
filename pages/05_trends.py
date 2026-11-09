"""Root pages delegator for 05_trends."""

import importlib
import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

trends_module = importlib.import_module("src.dashboard.pages.05_trends")
if hasattr(trends_module, "render"):
    trends_module.render()

