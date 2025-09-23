"""Compatibility shim to load the doorbell app as a plain pyscript module."""

# Importing the module registers its @service and @state_trigger handlers.
from apps.doorbell import *  # noqa: F401,F403
