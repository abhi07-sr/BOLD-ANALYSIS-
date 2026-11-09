"""Root pages delegator for 07_capital."""

import importlib
import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

capital_module = importlib.import_module("src.dashboard.pages.07_capital")
if hasattr(capital_module, "render"):
    capital_module.render()

