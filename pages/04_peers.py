"""Root pages delegator for 04_peers."""

import importlib
import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

peers_module = importlib.import_module("src.dashboard.pages.04_peers")
if hasattr(peers_module, "render"):
    peers_module.render()

