#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# make-duplex — Harpreet444/make-duplex
"""Convenience launcher: python run.py"""

import os
import sys

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from make_duplex.main import main

if __name__ == "__main__":
    main()
