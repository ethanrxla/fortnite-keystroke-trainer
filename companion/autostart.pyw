"""Windowless launcher for the login entry: keeps the overlay watcher running. See keystroke_lab/autostart.py."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

from keystroke_lab import autostart  # noqa: E402

if autostart.single_instance():
    autostart.watch()
