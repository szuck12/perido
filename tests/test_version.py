# test_version.py
# Guards against drift between the installed distribution and the module.

from __future__ import annotations

import importlib.metadata

import perido


def test_installed_metadata_matches_module_version():
    assert importlib.metadata.version("perido") == perido.__version__
