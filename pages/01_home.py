"""Root pages delegator for 01_home."""

import importlib
import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

home_module = importlib.import_module("src.dashboard.pages.01_home")
if hasattr(home_module, "render"):
    home_module.render()

