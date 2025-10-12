# Pyscript app: doorbell services (apps mode)
# - shelves_doorbell_flash_py: wrapper your YAML calls use
# - shelves_flash: real flasher (turn_on / turn_off with delays)
# - sonos_doorbell_chime_py / sonos_ding: stub chime you can expand later
#
# NOTE: Do not import helpers; Pyscript injects @service, log, task, service, etc.

import asyncio
import time
from time import monotonic

_DEFAULT_SHELF_TARGETS = [
    "light.shelf_1",
    "light.shelf_2",
    "light.shelf_3",
    "light.shelf_4",
]

_COLOR_NAME_MAP = {
    "red": (255, 0, 0),
    "blue": (0, 0, 255),
    "green": (0, 255, 0),
    "white": (255, 255, 255),
    "warm_white": (0, 0, 0, 255),
    "cool_white": (0, 0, 0, 0, 255),
    "amber": (255, 191, 0),
    "purple": (128, 0, 128),
}

_doorbell_guard_lock = asyncio.Lock()
_doorbell_last_run = 0.0


def _normalize_targets(targets):
    if not targets:
        return []
    if isinstance(targets, str):
        cleaned = []
        for raw in targets.split(","):
            stripped = raw.strip()
            if stripped:
                cleaned.append(stripped)
        return cleaned
    if isinstance(targets, (list, tuple, set)):
        cleaned = []
        for raw in targets:
            if raw is None:
                continue
            cleaned.append(str(raw))
        return cleaned
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
    scaled = int(round(255 * (pct_value / 100.0)))
    if scaled <= 0:
        return 1
    if scaled > 255:
        return 255
    return scaled


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


def _normalize_color_modes(modes):
    normalized = []
    if not modes:
        return normalized
    if isinstance(modes, (list, tuple, set)):
        iterable = modes
    else:
        iterable = [modes]
    for mode in iterable:
        try:
            normalized.append(str(mode).lower())
        except Exception:  # pragma: no cover - defensive
            continue
    return normalized


def _preferred_color_payload_mode(modes, current_mode=None):
    normalized = _normalize_color_modes(modes)
    if current_mode:
        try:
            current_normalized = str(current_mode).lower()
        except Exception:
            current_normalized = None
        if current_normalized:
            if current_normalized in {"rgbww", "rgbw", "rgb"}:
                return current_normalized
            if "rgb" in current_normalized:
                return "rgb"
    preferred_order = ("rgbww", "rgbw", "rgb")
    for target_mode in preferred_order:
        for candidate in normalized:
            if candidate == target_mode:
                return target_mode
    for candidate in normalized:
        if "rgb" in candidate:
            return "rgb"
    for candidate in normalized:
        if candidate == "hs" or candidate == "xy":
            return "rgb"
    return "rgb"


def _parse_color(color_value):
    default_rgb = (255, 0, 0)
    default_label = "red"
    if color_value is None:
        return list(default_rgb), default_label, []

    values = []
    label = str(color_value)

    if isinstance(color_value, dict):
        for key in ("rgbww_color", "rgbw_color", "rgb_color"):
            if key in color_value:
                payload = color_value.get(key)
                if isinstance(payload, (list, tuple, set)):
                    for item in payload:
                        values.append(item)
                else:
                    values.append(payload)
                label = key
                break
    elif isinstance(color_value, (list, tuple, set)):
        for item in color_value:
            values.append(item)
    elif isinstance(color_value, str):
        stripped = color_value.strip()
        if stripped:
            lower = stripped.lower()
            if lower in _COLOR_NAME_MAP:
                named = _COLOR_NAME_MAP[lower]
                for channel in named:
                    values.append(channel)
            elif stripped.startswith("#"):
                hex_value = stripped.lstrip("#")
                index = 0
                while index + 2 <= len(hex_value):
                    chunk = hex_value[index : index + 2]
                    try:
                        values.append(int(chunk, 16))
                    except ValueError:
                        values = []
                        break
                    index += 2
            else:
                cleaned = stripped.strip("[]()")
                parts = cleaned.split(",")
                for part in parts:
                    stripped_part = part.strip()
                    if not stripped_part:
                        continue
                    try:
                        values.append(int(float(stripped_part)))
                    except (TypeError, ValueError):
                        values = list(default_rgb)
                        break
    else:
        try:
            values.append(int(float(color_value)))
        except (TypeError, ValueError):
            values = list(default_rgb)

    if len(values) < 3:
        values = list(default_rgb)

    rgb_channels = []
    for raw in values[:3]:
        try:
            numeric = int(float(raw))
        except (TypeError, ValueError):
            numeric = 0
        if numeric < 0:
            numeric = 0
        elif numeric > 255:
            numeric = 255
        rgb_channels.append(numeric)

    while len(rgb_channels) < 3:
        rgb_channels.append(0)

    extras = []
    for raw in values[3:]:
        try:
            numeric = int(float(raw))
        except (TypeError, ValueError):
            numeric = 0
        if numeric < 0:
            numeric = 0
        elif numeric > 255:
            numeric = 255
        extras.append(numeric)

    return rgb_channels, label, extras


def _describe_light(entity_id):
    try:
        attrs = state.getattr(entity_id) or {}
    except Exception as err:  # pragma: no cover - defensive logging
        log.warning("shelves_apply: failed to read attributes for %s: %s", entity_id, err)
        return None

    supported_features = attrs.get("supported_features", 0)
    supported_color_modes = _normalize_color_modes(attrs.get("supported_color_modes"))
    current_color_mode = attrs.get("color_mode")

    supports_brightness = bool(supported_features & 1)
    for mode_name in supported_color_modes:
        if mode_name == "brightness" or "brightness" in mode_name:
            supports_brightness = True
            break

    supports_color = False
    for mode_name in supported_color_modes:
        if mode_name in {"hs", "rgb", "rgbw", "rgbww", "xy"}:
            supports_color = True
            supports_brightness = True
            break
        if "rgb" in mode_name:
            supports_color = True
            supports_brightness = True
            break

    normalized_current = None
    if current_color_mode:
        try:
            normalized_current = str(current_color_mode).lower()
        except Exception:
            normalized_current = None
    if normalized_current:
        if normalized_current == "brightness" or "brightness" in normalized_current:
            supports_brightness = True
        if (
            normalized_current in {"hs", "rgb", "rgbw", "rgbww", "xy"}
            or "rgb" in normalized_current
        ):
            supports_color = True
            supports_brightness = True
            present = False
            for mode_name in supported_color_modes:
                if mode_name == normalized_current:
                    present = True
                    break
            if not present:
                supported_color_modes.append(normalized_current)

    preferred_mode = None
    if supports_color:
        preferred_mode = _preferred_color_payload_mode(
            supported_color_modes,
            current_color_mode,
        )

    return {
        "supports_color": supports_color,
        "supports_brightness": supports_brightness,
        "preferred_color_mode": preferred_mode,
    }


def _collect_target_details(entity_ids):
    color_rgb = []
    color_rgbw = []
    color_rgbww = []
    brightness_only = []
    no_brightness = []
    switches = []
    missing = []
    unsupported = []
    ordered_lights = []

    for raw in entity_ids:
        entity_id = str(raw)
        if not entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        try:
            entity_state = state.get(entity_id)
        except Exception:
            entity_state = None
        if entity_state in (None, "unknown", "unavailable"):
            missing.append(entity_id)
            continue
        if domain == "light":
            description = _describe_light(entity_id)
            if description is None:
                missing.append(entity_id)
                continue
            ordered_lights.append(entity_id)
            if description.get("supports_color"):
                preferred = description.get("preferred_color_mode") or "rgb"
                if preferred == "rgbww":
                    color_rgbww.append(entity_id)
                elif preferred == "rgbw":
                    color_rgbw.append(entity_id)
                else:
                    color_rgb.append(entity_id)
            elif description.get("supports_brightness"):
                brightness_only.append(entity_id)
            else:
                no_brightness.append(entity_id)
        elif domain == "switch":
            switches.append(entity_id)
        else:
            unsupported.append(entity_id)

    return {
        "color_rgb": color_rgb,
        "color_rgbw": color_rgbw,
        "color_rgbww": color_rgbww,
        "brightness": brightness_only,
        "no_brightness": no_brightness,
        "switches": switches,
        "missing": missing,
        "unsupported": unsupported,
        "ordered_lights": ordered_lights,
    }


def _extra_channel(extra_channels, index):
    if index < 0:
        return 0
    current_index = 0
    for value in extra_channels:
        if current_index == index:
            try:
                numeric = int(float(value))
            except (TypeError, ValueError):
                numeric = 0
            if numeric < 0:
                numeric = 0
            elif numeric > 255:
                numeric = 255
            return numeric
        current_index += 1
    return 0


def _copy_rgb(rgb_color):
    copied = []
    for value in rgb_color:
        try:
            numeric = int(float(value))
        except (TypeError, ValueError):
            numeric = 0
        if numeric < 0:
            numeric = 0
        elif numeric > 255:
            numeric = 255
        copied.append(numeric)
    return copied


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
async def shelves_apply_py(
    targets=None,
    entity_id=None,
    group=None,
    brightness_pct: int = 100,
    transition: float = 0.0,
    rgbw=None,
    color=None,
    **kwargs,
):
    raw_ids = []
    for source in (targets, entity_id, group):
        raw_ids.extend(_normalize_targets(source))

    for key, value in kwargs.items():
        if isinstance(key, str) and key.startswith(("light.", "switch.", "group.")):
            raw_ids.append(key)
        elif key == "targets":
            raw_ids.extend(_normalize_targets(value))

    if not raw_ids:
        raw_ids = list(_DEFAULT_SHELF_TARGETS)

    ids = []
    seen = set()
    for candidate in raw_ids:
        if candidate not in seen:
            ids.append(candidate)
            seen.add(candidate)

    details = _collect_target_details(ids)

    missing = details["missing"]
    unsupported = details["unsupported"]
    color_rgb = details["color_rgb"]
    color_rgbw = details["color_rgbw"]
    color_rgbww = details["color_rgbww"]
    brightness_only = details["brightness"]
    no_brightness = details["no_brightness"]
    switches = details["switches"]

    if missing:
        log.warning(
            "shelves_apply_py: skipping unavailable targets: %s", ", ".join(missing)
        )
    if unsupported:
        log.warning(
            "shelves_apply_py: ignoring unsupported domains: %s", ", ".join(unsupported)
        )

    if not (
        color_rgb
        or color_rgbw
        or color_rgbww
        or brightness_only
        or no_brightness
        or switches
    ):
        log.error("shelves_apply_py: no usable targets after filtering")
        raise ValueError("shelves_apply_py: no usable targets")

    brightness_pct_value = max(1, min(100, int(brightness_pct or 0)))
    transition_value = max(0.0, float(transition or 0.0))

    if color is not None:
        rgb_color, color_label, extra_channels = _parse_color(color)
    else:
        parsed = _parse_color(rgbw)
        rgb_color = parsed[0]
        color_label = parsed[1]
        extra_channels = parsed[2]

    log.info(
        "shelves_apply_py: applying %s (brightness_pct=%s transition=%s) to %s",
        color_label,
        brightness_pct_value,
        transition_value,
        ", ".join(ids),
    )

    if color_rgb:
        payload = _copy_rgb(rgb_color)
        service.call(
            "light",
            "turn_on",
            entity_id=color_rgb,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
            rgb_color=payload,
        )

    if color_rgbw:
        payload = _copy_rgb(rgb_color)
        payload.append(_extra_channel(extra_channels, 0))
        service.call(
            "light",
            "turn_on",
            entity_id=color_rgbw,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
            rgbw_color=payload,
        )

    if color_rgbww:
        payload = _copy_rgb(rgb_color)
        payload.append(_extra_channel(extra_channels, 0))
        payload.append(_extra_channel(extra_channels, 1))
        service.call(
            "light",
            "turn_on",
            entity_id=color_rgbww,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
            rgbww_color=payload,
        )

    if brightness_only:
        service.call(
            "light",
            "turn_on",
            entity_id=brightness_only,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
        )

    if no_brightness:
        service.call(
            "light",
            "turn_on",
            entity_id=no_brightness,
        )

    if switches:
        service.call("switch", "turn_on", entity_id=switches)


@service
async def shelves_doorbell_flash_py(**kw):
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

    ids = []
    seen_ids = set()
    for candidate in raw_ids:
        if candidate not in seen_ids:
            ids.append(candidate)
            seen_ids.add(candidate)

    flashes_value = max(1, int(flashes))
    brightness_value = max(1, min(255, int(brightness)))
    on_s = max(0.05, float(on_ms) / 1000.0)
    off_s = max(0.05, float(off_ms) / 1000.0)

    if color is None:
        color = kwargs.get("color")

    color_requested = color is not None
    rgb_color, color_label, extra_channels = _parse_color(color)

    await task.unique("shelves_flash", kill_me=True)

    details = _collect_target_details(ids)

    lights_with_color = []
    lights_with_color.extend(details["color_rgb"])
    lights_with_color.extend(details["color_rgbw"])
    lights_with_color.extend(details["color_rgbww"])

    brightness_only = details["brightness"]
    lights_without_brightness = details["no_brightness"]
    switches = details["switches"]
    missing = details["missing"]
    unsupported = details["unsupported"]
    ordered_lights = details["ordered_lights"]

    if missing:
        log.warning(
            "shelves_flash: skipping unavailable targets: %s", ", ".join(missing)
        )
    if unsupported:
        log.warning(
            "shelves_flash: ignoring unsupported domains: %s", ", ".join(unsupported)
        )

    available = []
    for entity_id in lights_with_color:
        available.append(entity_id)
    for entity_id in brightness_only:
        available.append(entity_id)
    for entity_id in lights_without_brightness:
        available.append(entity_id)
    for entity_id in switches:
        available.append(entity_id)

    if color_requested:
        unsupported_color_entities = []
        for entity_id in brightness_only:
            unsupported_color_entities.append(entity_id)
        for entity_id in lights_without_brightness:
            unsupported_color_entities.append(entity_id)
        for entity_id in switches:
            unsupported_color_entities.append(entity_id)

        if not lights_with_color:
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

        for entity_id in details["color_rgbww"]:
            payload = _copy_rgb(rgb_color)
            payload.append(_extra_channel(extra_channels, 0))
            payload.append(_extra_channel(extra_channels, 1))
            log.info(
                "shelves_flash: using rgbww_color %s for %s",
                payload,
                entity_id,
            )
        for entity_id in details["color_rgbw"]:
            payload = _copy_rgb(rgb_color)
            payload.append(_extra_channel(extra_channels, 0))
            log.info(
                "shelves_flash: using rgbw_color %s for %s",
                payload,
                entity_id,
            )
        for entity_id in details["color_rgb"]:
            payload = _copy_rgb(rgb_color)
            log.info(
                "shelves_flash: using rgb_color %s for %s",
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

    for index in range(flashes_value):
        if details["color_rgb"]:
            service.call(
                "light",
                "turn_on",
                entity_id=details["color_rgb"],
                brightness=brightness_value,
                rgb_color=_copy_rgb(rgb_color),
            )
        if details["color_rgbw"]:
            payload = _copy_rgb(rgb_color)
            payload.append(_extra_channel(extra_channels, 0))
            service.call(
                "light",
                "turn_on",
                entity_id=details["color_rgbw"],
                brightness=brightness_value,
                rgbw_color=payload,
            )
        if details["color_rgbww"]:
            payload = _copy_rgb(rgb_color)
            payload.append(_extra_channel(extra_channels, 0))
            payload.append(_extra_channel(extra_channels, 1))
            service.call(
                "light",
                "turn_on",
                entity_id=details["color_rgbww"],
                brightness=brightness_value,
                rgbww_color=payload,
            )
        if brightness_only:
            service.call(
                "light",
                "turn_on",
                entity_id=brightness_only,
                brightness=brightness_value,
            )
        if lights_without_brightness:
            service.call("light", "turn_on", entity_id=lights_without_brightness)
        if switches:
            service.call("switch", "turn_on", entity_id=switches)

        await task.sleep(on_s)

        lights_to_turn_off = []
        for entity_id in ordered_lights:
            if entity_id not in lights_to_turn_off:
                lights_to_turn_off.append(entity_id)
        for entity_id in brightness_only:
            if entity_id not in lights_to_turn_off:
                lights_to_turn_off.append(entity_id)
        for entity_id in lights_without_brightness:
            if entity_id not in lights_to_turn_off:
                lights_to_turn_off.append(entity_id)
        if lights_to_turn_off:
            service.call("light", "turn_off", entity_id=lights_to_turn_off)
        if switches:
            service.call("switch", "turn_off", entity_id=switches)
        if index < flashes_value - 1:
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
    await sonos_ding(**kw)


@service
async def sonos_ding(
    player: str | None = None,
    media_url: str | None = None,
    volume: float = 0.15,
    wait_s: float | None = None,
):
    wait_value = _parse_duration(wait_s)
    log.info(
        "Stub sonos_ding: player=%s volume=%s media_url=%s wait_s=%s",
        player,
        volume,
        media_url,
        wait_value,
    )

