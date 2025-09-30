"""Legacy aliases bridging old doorbell Pyscript services.

These helpers allow existing YAML automations and scripts that still reference
``pyscript.sonos_doorbell_chime`` / ``pyscript.shelves_flash`` /
``pyscript.doorbell_ring`` to keep working while the new async app module lives
in ``pyscript/apps/doorbell.py``.
"""

from __future__ import annotations

from typing import Any

from pyscript import service

LEGACY_TARGETS = {
    "sonos_doorbell_chime": "sonos_doorbell_chime_py",
    "shelves_flash": "shelves_doorbell_flash_py",
    "doorbell_ring": "doorbell_ring_py",
}


async def _call_legacy(target: str, **kwargs: Any) -> None:
    """Invoke the updated Pyscript service backing a legacy alias."""

    log.debug("Redirecting legacy doorbell service %s to %s", target, LEGACY_TARGETS[target])
    await service.call("pyscript", LEGACY_TARGETS[target], **kwargs)


@service
async def sonos_doorbell_chime(**kwargs: Any) -> None:
    """Legacy alias for :func:`pyscript.sonos_doorbell_chime_py`."""

    await _call_legacy("sonos_doorbell_chime", **kwargs)


@service
async def shelves_flash(**kwargs: Any) -> None:
    """Legacy alias for :func:`pyscript.shelves_doorbell_flash_py`."""

    await _call_legacy("shelves_flash", **kwargs)


@service
async def doorbell_ring(**kwargs: Any) -> None:
    """Legacy alias for :func:`pyscript.doorbell_ring_py`."""

    await _call_legacy("doorbell_ring", **kwargs)
