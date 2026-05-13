"""Gymnasium-native MineRL package.

Importing :mod:`minerl` registers the built-in MineRL v1 task IDs with
Gymnasium. The Python layer is intentionally modern-only: it does not expose
the old Gym four-value step API.
"""

import logging

from minerl.envs.registration import register_all
from minerl.tasks.catalog import get_task, list_task_specs, list_tasks

logging.getLogger(__name__).addHandler(logging.NullHandler())

register_all()

__all__ = ["get_task", "list_task_specs", "list_tasks", "register_all"]
