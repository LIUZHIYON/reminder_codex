#!/usr/bin/env python3
"""Patched tts_node - fixes open_timeout in asyncio loop.create_connection"""

import sys
import os

# Ensure ROS Python packages are on path
_ros_pkg_path = "/opt/ros/humble/lib/python3.10/site-packages"
if _ros_pkg_path not in sys.path:
    sys.path.insert(0, _ros_pkg_path)

# Monkey-patch: make create_connection accept open_timeout
import asyncio as _asyncio
_original_create_connection = _asyncio.BaseEventLoop.create_connection

def _patched_create_connection(self, *args, **kwargs):
    kwargs.pop("open_timeout", None)
    return _original_create_connection(self, *args, **kwargs)

_asyncio.BaseEventLoop.create_connection = _patched_create_connection
print("[tts_patch] asyncio.BaseEventLoop.create_connection patched (open_timeout removed)", file=sys.stderr, flush=True)

# Now load and run the real tts_node
from robot_doubao_tts_node.tts_node import main
sys.exit(main())
