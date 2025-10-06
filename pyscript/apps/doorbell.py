# Pyscript app: doorbell services (apps mode)
# - shelves_doorbell_flash_py: wrapper your YAML calls use
# - shelves_flash: real flasher (turn_on / turn_off with delays)
# - sonos_doorbell_chime_py / sonos_ding: stub chime you can expand later
#
# NOTE: Do not import helpers; Pyscript injects @service, log, task, service, etc.

import asyncio
from time import monotonic

_DEFAULT_SHELF_TARGETS = [
    "light.shelf_1",
    "light.shelf_2",
    "light.shelf_3",
    "light.shelf_4",
]

_doorbell_guard_lock = asyncio.Lock()
_doorbell_last_run = 0.0

def _normalize_targets(targets):
    if not targets:
        return []
    if isinstance(targets, str):
        # allow "light.a, light.b"
        return [e.strip() for e in targets.split(",") if e.strip()]
    if isinstance(targets, (list, tuple, set)):
        return [str(e) for e in targets]
    return [str(targets)]


def _parse_duration(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        parts = stripped.split(":")
        try:
            if len(parts) == 3:
                hours, minutes, seconds = parts
            elif len(parts) == 2:
                hours = 0
                minutes, seconds = parts
            else:
                return max(0.0, float(stripped))
            total = (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
            return max(0.0, float(total))
        except (TypeError, ValueError):
            try:
                return max(0.0, float(stripped))
            except (TypeError, ValueError):
                return None
    return None


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "on", "yes", "y"}
    return bool(value)


def _pct_to_brightness(pct):
    try:
        pct_value = float(pct)
    except (TypeError, ValueError):
        pct_value = 0.0
    pct_value = max(0.0, min(100.0, pct_value))
    if pct_value <= 0.0:
        return 0
    return int(round(255 * (pct_value / 100.0))) or 1


def _to_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except (TypeError, ValueError):
            duration = _parse_duration(value)
            if duration is not None:
                return duration
    return default


@service
async def doorbell_ring_py(
    players=None,
    chime_url=None,
    chime_vol=0.4,
    chime_len=None,
    flash_repeats=3,
    flash_on_time_ms=250,
    flash_brightness_pct=50,
    flash_enabled=True,
    guard_seconds=4,
):
    guard = max(0.0, _to_float(guard_seconds, default=0.0))
    async with _doorbell_guard_lock:
        global _doorbell_last_run
        now = monotonic()
        if guard > 0 and (now - _doorbell_last_run) < guard:
            remaining = guard - (now - _doorbell_last_run)
            log.info(
                "doorbell_ring_py: guard active (%.2fs remaining); skipping", max(0.0, remaining)
            )
            return
        _doorbell_last_run = now

    player_ids = _normalize_targets(players)
    wait_s = _parse_duration(chime_len)
    sonos_tasks = []
    for player in player_ids:
        sonos_tasks.append(
            sonos_doorbell_chime_py(
                player=player,
                media_url=chime_url,
                volume=chime_vol,
                wait_s=wait_s,
            )
        )

    flash_tasks = []
    if _coerce_bool(flash_enabled):
        flashes = 0
        try:
            flashes = int(float(flash_repeats))
        except (TypeError, ValueError):
            flashes = 0
        if flashes > 0:
            brightness = _pct_to_brightness(flash_brightness_pct)
            if brightness > 0:
                on_ms = int(max(50, float(flash_on_time_ms or 0)))
                flash_tasks.append(
                    shelves_flash(
                        targets=_DEFAULT_SHELF_TARGETS,
                        flashes=flashes,
                        brightness=brightness,
                        on_ms=on_ms,
                        off_ms=on_ms,
                    )
                )

    pending = []
    if sonos_tasks:
        pending.extend(sonos_tasks)
    if flash_tasks:
        pending.extend(flash_tasks)

    if not pending:
        log.warning("doorbell_ring_py: nothing to do (no players or flash targets)")
        return

    await asyncio.gather(*pending)
@service
async def shelves_doorbell_flash_py(**kw):
    # wrapper for existing YAML calls
    await shelves_flash(**kw)

@service
async def shelves_flash(
    targets=None,
    entity_id=None,
    targets_group=None,
    flashes: int = 3,
    brightness: int = 230,
    on_ms: int = 200,
    off_ms: int = 200,
    restore: bool = True,
    color=None,
    **kwargs,
):
    raw_ids = []
    for source in (targets, entity_id, targets_group):
        raw_ids.extend(_normalize_targets(source))

    for key in kwargs:
        if isinstance(key, str) and key.startswith(("light.", "switch.", "group.")):
            raw_ids.append(key)

    if not raw_ids:
        raw_ids = ["light.shelves_all"]

    # dedupe while preserving order
    ids = []
    seen_ids = set()
    for candidate_id in raw_ids:
        if candidate_id not in seen_ids:
            ids.append(candidate_id)
            seen_ids.add(candidate_id)

    # clamp/convert inputs
    flashes = max(1, int(flashes))
    brightness = max(1, min(255, int(brightness)))
    on_s = max(0.05, float(on_ms) / 1000.0)
    off_s = max(0.05, float(off_ms) / 1000.0)

    if color is None:
        color = kwargs.get("color")

    color_requested = color is not None
    rgb_color, color_label, extra_channels = _parse_color(color)

    # ensure only one flasher runs at a time
    await task.unique("shelves_flash", kill_me=True)

    (
        lights_with_brightness,
        lights_without_brightness,
        switches,
        missing,
        unsupported,
    ) = _resolve_entities(ids)

    if missing:
        log.warning(
            "shelves_flash: skipping unavailable targets: %s", ", ".join(missing)
        )

    if unsupported:
        log.warning(
            "shelves_flash: ignoring unsupported domains: %s", ", ".join(unsupported)
        )

    color_capable_lights = []
    brightness_only_lights = []
    color_payload_modes = {}

    for entity_id in lights_with_brightness:
        try:
            entity_attributes = state.getattr(entity_id) or {}
        except Exception as err:  # pragma: no cover - defensive logging
            log.warning(
                "shelves_flash: error retrieving attributes for %s: %s", entity_id, err
            )
            entity_attributes = {}

        supported_color_modes = entity_attributes.get("supported_color_modes")
        current_color_mode = entity_attributes.get("color_mode")
        normalized_modes = _normalize_color_modes(supported_color_modes)

        supports_color = False
        for mode_str in normalized_modes:
            if mode_str in {"hs", "rgb", "rgbw", "rgbww", "xy"} or "rgb" in mode_str:
                supports_color = True
                break

        if not supports_color and current_color_mode:
            current_mode_normalized = str(current_color_mode).lower()
            if (
                current_mode_normalized in {"hs", "rgb", "rgbw", "rgbww", "xy"}
                or "rgb" in current_mode_normalized
            ):
                supports_color = True
                if current_mode_normalized not in normalized_modes:
                    normalized_modes = normalized_modes + [current_mode_normalized]

        if supports_color:
            color_capable_lights.append(entity_id)
            color_payload_modes[entity_id] = _preferred_color_payload_mode(
                normalized_modes,
                current_color_mode,
            )
        else:
            brightness_only_lights.append(entity_id)

    available = (
        color_capable_lights
        + brightness_only_lights
        + lights_without_brightness
        + switches
    )

    rgb_payload = []
    rgbw_payload = []
    rgbww_payload = []

    if color_capable_lights:
        for entity_id in color_capable_lights:
            mode = color_payload_modes.get(entity_id, "rgb")
            if mode == "rgbww":
                rgbww_payload.append(entity_id)
            elif mode == "rgbw":
                rgbw_payload.append(entity_id)
            else:
                rgb_payload.append(entity_id)

    if color_requested:
        unsupported_color_entities = (
            brightness_only_lights
            + lights_without_brightness
            + switches
        )
        if not color_capable_lights:
            log.warning(
                "shelves_flash: color '%s' requested but no color-capable lights available; continuing without color",
                color_label,
            )
        elif unsupported_color_entities:
            log.info(
                "shelves_flash: color '%s' requested but unsupported by: %s",
                color_label,
                ", ".join(unsupported_color_entities),
            )

        if color_capable_lights:
            for entity_id in color_capable_lights:
                mode = color_payload_modes.get(entity_id, "rgb")
                if mode == "rgbww":
                    payload = list(rgb_color) + [
                        extra_channels[0] if len(extra_channels) > 0 else 0,
                        extra_channels[1] if len(extra_channels) > 1 else 0,
                    ]
                    payload_key = "rgbww_color"
                elif mode == "rgbw":
                    payload = list(rgb_color) + [
                        extra_channels[0] if len(extra_channels) > 0 else 0
                    ]
                    payload_key = "rgbw_color"
                else:
                    payload = list(rgb_color)
                    payload_key = "rgb_color"
                log.info(
                    "shelves_flash: using %s %s for %s",
                    payload_key,
                    payload,
                    entity_id,
                )

    if not available:
        log.error("shelves_flash: no usable targets after filtering unavailable entities")
        raise ValueError("shelves_flash: no usable targets")

    restore_scene_entity = None
    if restore:
        scene_slug = f"shelves_flash_restore_{int(time.time() * 1000)}"
        try:
            service.call(
                "scene",
                "create",
                scene_id=scene_slug,
                snapshot_entities=available,
            )
            restore_scene_entity = f"scene.{scene_slug}"
        except Exception as err:  # pragma: no cover - defensive logging
            log.error("shelves_flash: failed to snapshot state for restore: %s", err)

    for i in range(flashes):
        if color_capable_lights:
            if rgb_payload:
                service.call(
                    "light",
                    "turn_on",
                    entity_id=rgb_payload,
                    brightness=brightness,
                    rgb_color=list(rgb_color),
                )

            if rgbw_payload:
                rgbw_color = list(rgb_color) + [
                    extra_channels[0] if len(extra_channels) > 0 else 0
                ]
                service.call(
                    "light",
                    "turn_on",
                    entity_id=rgbw_payload,
                    brightness=brightness,
                    rgbw_color=rgbw_color,
                )

            if rgbww_payload:
                rgbww_color = list(rgb_color) + [
                    extra_channels[0] if len(extra_channels) > 0 else 0,
                    extra_channels[1] if len(extra_channels) > 1 else 0,
                ]
                service.call(
                    "light",
                    "turn_on",
                    entity_id=rgbww_payload,
                    brightness=brightness,
                    rgbww_color=rgbww_color,
                )
        if brightness_only_lights:
            service.call(
                "light",
                "turn_on",
                entity_id=brightness_only_lights,
                brightness=brightness,
            )
        if lights_without_brightness:
            service.call("light", "turn_on", entity_id=lights_without_brightness)
        if switches:
            service.call("switch", "turn_on", entity_id=switches)

        await task.sleep(on_s)

        all_lights = (
            color_capable_lights
            + brightness_only_lights
            + lights_without_brightness
        )
        if all_lights:
            service.call("light", "turn_off", entity_id=all_lights)
        if switches:
            service.call("switch", "turn_off", entity_id=switches)
        if i < flashes - 1:
            await task.sleep(off_s)

    if restore and restore_scene_entity:
        try:
            service.call("scene", "turn_on", entity_id=restore_scene_entity)
        except Exception as err:  # pragma: no cover - defensive logging
            log.error(
                "shelves_flash: failed to restore snapshot scene %s: %s",
                restore_scene_entity,
                err,
            )

@service
async def sonos_doorbell_chime_py(**kw):
    # wrapper for existing YAML calls
    await sonos_ding(**kw)

@service
async def sonos_ding(
    player: str | None = None,
    media_url: str | None = None,
    volume: float = 0.15,
    wait_s: float | None = None,
):
    # stub: swap in real chime logic when ready
    wait_value = _parse_duration(wait_s)
    log.info(
        "Stub sonos_ding: player=%s volume=%s media_url=%s wait_s=%s",
        player,
        volume,
        media_url,
        wait_value,
    )
