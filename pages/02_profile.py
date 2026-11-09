"""Root pages delegator for 02_profile."""

import importlib
import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

profile_module = importlib.import_module("src.dashboard.pages.02_profile")
if hasattr(profile_module, "render"):
    profile_module.render()

