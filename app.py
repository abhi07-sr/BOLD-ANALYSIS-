"""Workspace root entry point for Streamlit dashboard."""

import os
import sys

_WORKSPACE_ROOT = os.path.abspath(os.path.dirname(__file__))
if _WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, _WORKSPACE_ROOT)

import runpy

app_path = os.path.join(_WORKSPACE_ROOT, "src", "dashboard", "app.py")
runpy.run_path(app_path, run_name="__main__")

