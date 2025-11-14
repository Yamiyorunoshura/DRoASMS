#!/usr/bin/env python3
"""
Spec-compatible Cython compiler entrypoint.

This thin wrapper exists to satisfy the OpenSpec requirement that the project
provides a dedicated `scripts/cython_compiler.py` entrypoint. It simply
delegates to the implementation in `compile_modules.py`, so both
`scripts/compile_modules.py` and `scripts/cython_compiler.py` share the same
CLI semantics (including --optimize/--parallel/--incremental).
"""

from __future__ import annotations

from compile_modules import main as _main

if __name__ == "__main__":
    _main()
