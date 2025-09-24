"""Doorbell chime automation implemented with Pyscript.

This pared-down module focuses solely on playing the Sonos chime. The shelves
flash sequence will return in a follow-up iteration once the audio path is
stable.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Iterable, Mapping

from pyscript import log, service, state, state_trigger, task, task_unique

DEFAULT_CHIME_URL = "http://192.168.68.86:8123/local/dingdong.mp3"
DEFAULT_CHIME_VOL = 0.4
DEFAULT_CHIME_DURATION = timedelta(seconds=3)
DEFAULT_PLAYERS = ("media_player.kitchen", "media_player.patio")

EVENT_ENTITY = "event.front_door_ding"
TASK_NAME = "doorbell_ringing_flow"
MOTION_CLEAR = {None, False, "false", "False"}
VALID_KINDS = {None, "ding", "doorbell", "on_demand_ding", "remote_ding"}
VALID_STATES = {None, "ringing", "starting", "doorbell", "button", "on_demand"}
VALID_BUTTON_STATES = {"ringing", "pressed", "start"}


def _coerce_mapping(value: Any) -> dict[str, Any]:
    """Return a dict whether Home Assistant hands us a dict or JSON string."""

    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {}


def _flatten_entities(value: Any) -> list[str]:
    """Normalise entity inputs into a unique list of media_player IDs."""

    result: list[str] = []

    def _walk(item: Any) -> None:
        if isinstance(item, Mapping) and "entity_id" in item:
            _walk(item["entity_id"])
            return
        if isinstance(item, str):
            stripped = item.strip()
            if not stripped:
                return
            if stripped.startswith("["):
                try:
                    decoded = json.loads(stripped)
                except ValueError:
                    result.append(stripped)
                    return
                _walk(decoded)
                return
            result.append(stripped)
            return
        if isinstance(item, Iterable) and not isinstance(item, (str, bytes)):
            for inner in item:
                _walk(inner)
            return
        if item is not None:
            result.append(str(item))

    if value is None:
        result.extend(DEFAULT_PLAYERS)
    else:
        _walk(value)

    seen: set[str] = set()
    unique: list[str] = []
    for entity in result or list(DEFAULT_PLAYERS):
        if entity not in seen:
            seen.add(entity)
            unique.append(entity)
    return unique


def _parse_duration(value: Any) -> float:
    """Accept seconds, HH:MM:SS strings, or timedeltas and return seconds."""

    if value is None:
        return DEFAULT_CHIME_DURATION.total_seconds()
    if isinstance(value, timedelta):
        return max(value.total_seconds(), 0.0)
    if isinstance(value, (int, float)):
        return max(float(value), 0.0)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return DEFAULT_CHIME_DURATION.total_seconds()
        parts = text.split(":")
        try:
            if len(parts) == 3:
                hours, minutes, seconds = parts
            elif len(parts) == 2:
                hours = "0"
                minutes, seconds = parts
            elif len(parts) == 1:
                hours = "0"
                minutes = "0"
                seconds = parts[0]
            else:
                raise ValueError
            total = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return max(total, 0.0)
        except ValueError as exc:
            raise ValueError(f"Cannot parse duration from {value!r}") from exc
    raise ValueError(f"Unsupported duration type: {type(value)!r}")


async def _run_sonos_doorbell_chime(
    players: Any = None,
    chime_url: str = DEFAULT_CHIME_URL,
    chime_vol: float = DEFAULT_CHIME_VOL,
    chime_len: Any = "00:00:03",
) -> None:
    """Play the doorbell chime across the requested Sonos players."""

    player_list = _flatten_entities(players)
    if not player_list:
        log.warning("Doorbell chime skipped: no Sonos players resolved")
        return

    try:
        chime_seconds = _parse_duration(chime_len)
    except ValueError:
        log.warning(
            "Invalid chime_len %r; falling back to %s", chime_len, DEFAULT_CHIME_DURATION
        )
        chime_seconds = DEFAULT_CHIME_DURATION.total_seconds()

    volume_level = max(0.0, min(float(chime_vol), 1.0))

    await service.call("sonos", "snapshot", entity_id=player_list, with_group=True)

    for entity_id in player_list:
        await service.call(
            "media_player",
            "volume_set",
            entity_id=entity_id,
            volume_level=volume_level,
        )

    for entity_id in player_list:
        await service.call(
            "media_player",
            "play_media",
            entity_id=entity_id,
            media_content_id=chime_url,
            media_content_type="music",
        )
        await task.sleep(0.2)

    await task.sleep(chime_seconds)
    await service.call("sonos", "restore", entity_id=player_list, with_group=True)


@service
async def sonos_doorbell_chime_py(
    players: Any = None,
    chime_url: str = DEFAULT_CHIME_URL,
    chime_vol: float = DEFAULT_CHIME_VOL,
    chime_len: Any = "00:00:03",
) -> None:
    """Expose the chime helper as a callable Pyscript service."""

    await _run_sonos_doorbell_chime(players, chime_url, chime_vol, chime_len)


@state_trigger(f"{EVENT_ENTITY} != ''", state_check_now=False)
@task_unique(TASK_NAME)
async def ring_doorbell_handler(value: str | None = None, **kwargs: Any) -> None:
    """Filter Ring ding events and play the Sonos chime once per press."""

    attrs = state.getattr(EVENT_ENTITY) or {}
    event_type = attrs.get("event_type")
    data = _coerce_mapping(attrs.get("event_data"))

    ring_kind = data.get("kind")
    ring_state = data.get("state")
    ring_button_state = data.get("doorbellStatus")
    ring_motion = data.get("motion")

    if event_type != "ding":
        return
    if ring_kind not in VALID_KINDS:
        return
    if ring_state not in VALID_STATES and ring_button_state not in VALID_BUTTON_STATES:
        return
    if ring_motion not in MOTION_CLEAR:
        return

    log.info("Ring ding detected (kind=%s state=%s)", ring_kind, ring_state)

    await _run_sonos_doorbell_chime()
    await task.sleep(4.0)
