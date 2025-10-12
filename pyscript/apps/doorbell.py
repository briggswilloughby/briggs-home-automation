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

_doorbell_guard_lock = asyncio.Lock()
_doorbell_last_run = 0.0

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

def _normalize_targets(targets):
    if not targets:
        return []
    if isinstance(targets, str):
        # allow "light.a, light.b"
        cleaned = []
        for element in targets.split(","):
            stripped = element.strip()
            if stripped:
                cleaned.append(stripped)
        return cleaned
    if isinstance(targets, (list, tuple, set)):
        cleaned = []
        for element in targets:
            cleaned.append(str(element))
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


def _parse_rgbw_values(value):
    if value is None:
        return [0, 0, 0, 0, 0]
    if isinstance(value, str):
        cleaned = value.strip().strip("[]()")
        if not cleaned:
            parts = []
        else:
            parts = []
            for segment in cleaned.split(","):
                parts.append(segment.strip())
    elif isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            parts.append(item)
    else:
        parts = [value]

    numeric = []
    for part in parts:
        if part in (None, ""):
            continue
        try:
            numeric.append(int(float(part)))
        except (TypeError, ValueError):
            numeric.append(0)

    while len(numeric) < 5:
        numeric.append(0)

    clamped = []
    for item in numeric[:5]:
        try:
            integer_value = int(item)
        except (TypeError, ValueError):
            integer_value = 0
        if integer_value < 0:
            integer_value = 0
        elif integer_value > 255:
            integer_value = 255
        clamped.append(integer_value)

    return clamped


def _normalize_color_modes(modes):
    if not modes:
        return []
    if isinstance(modes, (list, tuple, set)):
        iterable = modes
    else:
        iterable = [modes]
    normalized = []
    for mode in iterable:
        try:
            normalized.append(str(mode).lower())
        except Exception:  # pragma: no cover - defensive
            continue
    return normalized


def _preferred_color_payload_mode(modes, current_mode=None):
    normalized = _normalize_color_modes(modes)
    if current_mode:
        current_normalized = str(current_mode).lower()
        if current_normalized in {"rgbww", "rgbw", "rgb"}:
            return current_normalized
        if "rgb" in current_normalized:
            return "rgb"
    for preferred in ("rgbww", "rgbw", "rgb"):
        for mode in normalized:
            if mode == preferred:
                return preferred
    for mode in normalized:
        if "rgb" in mode:
            return "rgb"
    for mode in normalized:
        if mode in {"hs", "xy"}:
            return "rgb"
    return "rgb"


def _parse_color(color):
    default_rgb = (255, 0, 0)
    default_label = "red"
    if color is None:
        return default_rgb, default_label, []

    values = []
    label = str(color)

    if isinstance(color, dict):
        for key in ("rgbww_color", "rgbw_color", "rgb_color"):
            if key in color:
                values = list(color.get(key) or [])
                label = key
                break
    elif isinstance(color, (list, tuple, set)):
        values = list(color)
    elif isinstance(color, str):
        stripped = color.strip()
        if not stripped:
            values = []
        else:
            lower = stripped.lower()
            if lower in _COLOR_NAME_MAP:
                values = list(_COLOR_NAME_MAP[lower])
            elif stripped.startswith("#"):
                hex_value = stripped.lstrip("#")
                if len(hex_value) in {6, 8, 10}:
                    try:
                        values = []
                        index = 0
                        while index < len(hex_value):
                            chunk = hex_value[index : index + 2]
                            values.append(int(chunk, 16))
                            index += 2
                    except ValueError:
                        values = []
                else:
                    values = []
            else:
                cleaned = stripped.strip("[]()")
                parts = []
                for segment in cleaned.split(","):
                    stripped_segment = segment.strip()
                    if stripped_segment:
                        parts.append(stripped_segment)
                values = []
                for part in parts:
                    try:
                        values.append(int(float(part)))
                    except (TypeError, ValueError):
                        values = list(default_rgb)
                        break
    else:
        values = []

    if len(values) < 3:
        values = list(default_rgb)

    rgb_values = []
    for raw_value in values[:3]:
        try:
            numeric_value = int(float(raw_value))
        except (TypeError, ValueError):
            numeric_value = 0
        clamped_value = max(0, min(255, numeric_value))
        rgb_values.append(clamped_value)

    while len(rgb_values) < 3:
        rgb_values.append(0)

    extras = []
    for raw_extra in values[3:]:
        try:
            numeric_extra = int(float(raw_extra))
        except (TypeError, ValueError):
            numeric_extra = 0
        clamped_extra = max(0, min(255, numeric_extra))
        extras.append(clamped_extra)

    return tuple(rgb_values), label, extras


def _copy_rgb(rgb_color):
    rgb_list = []
    for channel in rgb_color:
        try:
            numeric_value = int(float(channel))
        except (TypeError, ValueError):
            numeric_value = 0
        if numeric_value < 0:
            numeric_value = 0
        elif numeric_value > 255:
            numeric_value = 255
        rgb_list.append(numeric_value)
    return rgb_list


def _extra_channel(extra_channels, index):
    if index < 0:
        return 0
    current_index = 0
    for value in extra_channels:
        if current_index == index:
            try:
                numeric_value = int(float(value))
            except (TypeError, ValueError):
                numeric_value = 0
            if numeric_value < 0:
                numeric_value = 0
            elif numeric_value > 255:
                numeric_value = 255
            return numeric_value
        current_index += 1
    return 0


def _describe_light(entity_id):
    try:
        attrs = state.getattr(entity_id) or {}
    except Exception as err:  # pragma: no cover - defensive logging
        log.warning(
            "shelves_apply: error retrieving attributes for %s: %s",
            entity_id,
            err,
        )
        return None

    supported_features = attrs.get("supported_features", 0)
    supported_color_modes = _normalize_color_modes(attrs.get("supported_color_modes"))
    current_color_mode = attrs.get("color_mode")

    supports_brightness = False
    if supported_features & 1:
        supports_brightness = True

    for mode_name in supported_color_modes:
        if mode_name == "brightness" or "brightness" in mode_name:
            supports_brightness = True
        if mode_name in {"hs", "rgb", "rgbw", "rgbww", "xy"}:
            supports_brightness = True
            return {
                "supports_brightness": supports_brightness,
                "supports_color": True,
                "preferred_color_mode": _preferred_color_payload_mode(
                    supported_color_modes,
                    current_color_mode,
                ),
            }
        if "rgb" in mode_name:
            supports_brightness = True
            return {
                "supports_brightness": supports_brightness,
                "supports_color": True,
                "preferred_color_mode": _preferred_color_payload_mode(
                    supported_color_modes,
                    current_color_mode,
                ),
            }

    normalized_current = None
    if current_color_mode:
        normalized_current = str(current_color_mode).lower()
        if normalized_current == "brightness" or "brightness" in normalized_current:
            supports_brightness = True

    supports_color = False
    if normalized_current and (
        normalized_current in {"hs", "rgb", "rgbw", "rgbww", "xy"}
        or "rgb" in normalized_current
    ):
        supports_color = True
        supports_brightness = True
        if normalized_current not in supported_color_modes:
            updated_modes = []
            for existing_mode in supported_color_modes:
                updated_modes.append(existing_mode)
            updated_modes.append(normalized_current)
            supported_color_modes = updated_modes

    if supports_color:
        preferred_mode = _preferred_color_payload_mode(
            supported_color_modes,
            current_color_mode,
        )
        return {
            "supports_brightness": supports_brightness,
            "supports_color": True,
            "preferred_color_mode": preferred_mode,
        }

    for mode_name in supported_color_modes:
        if mode_name == "brightness" or "brightness" in mode_name:
            supports_brightness = True
            break

    return {
        "supports_brightness": supports_brightness,
        "supports_color": False,
        "preferred_color_mode": None,
    }


def _collect_target_details(entity_ids):
    color_rgb = []
    color_rgbw = []
    color_rgbww = []
    brightness_only = []
    lights_without_brightness = []
    switches = []
    missing = []
    unsupported = []
    ordered_lights = []

    for entity in entity_ids:
        entity_id = str(entity)
        domain = entity_id.split(".", 1)[0]
        try:
            entity_state = state.get(entity_id)
        except Exception:  # pragma: no cover - defensive
            entity_state = None

        if entity_state in (None, "unknown", "unavailable"):
            missing.append(entity_id)
            continue

        if domain == "light":
            description = _describe_light(entity_id)
            if description is None:
                missing.append(entity_id)
                continue

            if description["supports_color"]:
                preferred_mode = description.get("preferred_color_mode") or "rgb"
                if preferred_mode == "rgbww":
                    color_rgbww.append(entity_id)
                elif preferred_mode == "rgbw":
                    color_rgbw.append(entity_id)
                else:
                    color_rgb.append(entity_id)
            elif description["supports_brightness"]:
                brightness_only.append(entity_id)
            else:
                lights_without_brightness.append(entity_id)
            ordered_lights.append(entity_id)
        elif domain == "switch":
            switches.append(entity_id)
        else:
            unsupported.append(entity_id)

    return {
        "color_rgb": color_rgb,
        "color_rgbw": color_rgbw,
        "color_rgbww": color_rgbww,
        "brightness": brightness_only,
        "no_brightness": lights_without_brightness,
        "switches": switches,
        "missing": missing,
        "unsupported": unsupported,
        "ordered_lights": ordered_lights,
    }


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
    seen_ids = set()
    for candidate_id in raw_ids:
        if candidate_id not in seen_ids:
            ids.append(candidate_id)
            seen_ids.add(candidate_id)

    details = _collect_target_details(ids)

    missing = details["missing"]
    unsupported = details["unsupported"]
    color_rgb = details["color_rgb"]
    color_rgbw = details["color_rgbw"]
    color_rgbww = details["color_rgbww"]
    brightness_only_lights = details["brightness"]
    lights_without_brightness = details["no_brightness"]
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
        or brightness_only_lights
        or lights_without_brightness
        or switches
    ):
        log.error("shelves_apply_py: no usable targets after filtering")
        raise ValueError("shelves_apply_py: no usable targets")

    brightness_pct_value = max(1, min(100, int(brightness_pct or 0)))
    transition_value = max(0.0, float(transition or 0.0))

    if color is not None:
        rgb_color, color_label, extra_channels = _parse_color(color)
    else:
        parsed_rgbw = _parse_rgbw_values(rgbw)
        rgb_color = tuple(parsed_rgbw[:3])
        extra_channels = parsed_rgbw[3:]
        color_label = f"rgbw {parsed_rgbw[:4]}"

    log.info(
        "shelves_apply_py: applying %s (brightness_pct=%s transition=%s) to %s",
        color_label,
        brightness_pct_value,
        transition_value,
        ", ".join(ids),
    )

    if color_rgb:
        payload_list = _copy_rgb(rgb_color)
        service.call(
            "light",
            "turn_on",
            entity_id=color_rgb,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
            rgb_color=payload_list,
        )

    if color_rgbw:
        rgbw_color = _copy_rgb(rgb_color)
        rgbw_color.append(_extra_channel(extra_channels, 0))
        service.call(
            "light",
            "turn_on",
            entity_id=color_rgbw,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
            rgbw_color=rgbw_color,
        )

    if color_rgbww:
        rgbww_color = _copy_rgb(rgb_color)
        rgbww_color.append(_extra_channel(extra_channels, 0))
        rgbww_color.append(_extra_channel(extra_channels, 1))
        service.call(
            "light",
            "turn_on",
            entity_id=color_rgbww,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
            rgbww_color=rgbww_color,
        )

    if brightness_only_lights:
        service.call(
            "light",
            "turn_on",
            entity_id=brightness_only_lights,
            brightness_pct=brightness_pct_value,
            transition=transition_value,
        )

    if lights_without_brightness:
        service.call(
            "light",
            "turn_on",
            entity_id=lights_without_brightness,
            transition=transition_value,
        )

    if switches:
        service.call("switch", "turn_on", entity_id=switches)

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

    details = _collect_target_details(ids)

    missing = details["missing"]
    unsupported = details["unsupported"]
    color_rgb = details["color_rgb"]
    color_rgbw = details["color_rgbw"]
    color_rgbww = details["color_rgbww"]
    brightness_only_lights = details["brightness"]
    lights_without_brightness = details["no_brightness"]
    switches = details["switches"]
    ordered_lights = details["ordered_lights"]

    if missing:
        log.warning(
            "shelves_flash: skipping unavailable targets: %s", ", ".join(missing)
        )

    if unsupported:
        log.warning(
            "shelves_flash: ignoring unsupported domains: %s", ", ".join(unsupported)
        )

    color_capable_lights = []
    for entity_id in color_rgb:
        color_capable_lights.append(entity_id)
    for entity_id in color_rgbw:
        color_capable_lights.append(entity_id)
    for entity_id in color_rgbww:
        color_capable_lights.append(entity_id)

    available = []
    for entity_id in color_capable_lights:
        available.append(entity_id)
    for entity_id in brightness_only_lights:
        available.append(entity_id)
    for entity_id in lights_without_brightness:
        available.append(entity_id)
    for entity_id in switches:
        available.append(entity_id)

    if color_requested:
        unsupported_color_entities = []
        for entity_id in brightness_only_lights:
            unsupported_color_entities.append(entity_id)
        for entity_id in lights_without_brightness:
            unsupported_color_entities.append(entity_id)
        for entity_id in switches:
            unsupported_color_entities.append(entity_id)

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

        for entity_id in color_capable_lights:
            payload_key = "rgb_color"
            payload = _copy_rgb(rgb_color)
            if entity_id in color_rgbww:
                payload_key = "rgbww_color"
                payload.append(_extra_channel(extra_channels, 0))
                payload.append(_extra_channel(extra_channels, 1))
            elif entity_id in color_rgbw:
                payload_key = "rgbw_color"
                payload.append(_extra_channel(extra_channels, 0))
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
        if color_rgb:
            service.call(
                "light",
                "turn_on",
                entity_id=color_rgb,
                brightness=brightness,
                rgb_color=_copy_rgb(rgb_color),
            )

        if color_rgbw:
            rgbw_color = _copy_rgb(rgb_color)
            rgbw_color.append(_extra_channel(extra_channels, 0))
            service.call(
                "light",
                "turn_on",
                entity_id=color_rgbw,
                brightness=brightness,
                rgbw_color=rgbw_color,
            )

        if color_rgbww:
            rgbww_color = _copy_rgb(rgb_color)
            rgbww_color.append(_extra_channel(extra_channels, 0))
            rgbww_color.append(_extra_channel(extra_channels, 1))
            service.call(
                "light",
                "turn_on",
                entity_id=color_rgbww,
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

        if ordered_lights or brightness_only_lights or lights_without_brightness:
            lights_to_turn_off = []
            for entity_id in ordered_lights:
                lights_to_turn_off.append(entity_id)
            for entity_id in brightness_only_lights:
                if entity_id not in lights_to_turn_off:
                    lights_to_turn_off.append(entity_id)
            for entity_id in lights_without_brightness:
                if entity_id not in lights_to_turn_off:
                    lights_to_turn_off.append(entity_id)
            if lights_to_turn_off:
                service.call("light", "turn_off", entity_id=lights_to_turn_off)
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
