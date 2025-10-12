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

# ---------- public: shelves_flash ----------

def _parse_rgbw_values(value):
    if value is None:
        return [0, 0, 0, 0, 0]
    if isinstance(value, str):
        cleaned = value.strip().strip("[]()")
        if not cleaned:
            parts = []
        else:
            parts = [segment.strip() for segment in cleaned.split(",")]
    elif isinstance(value, (list, tuple, set)):
        parts = list(value)
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

    return [max(0, min(255, int(v))) for v in numeric[:5]]


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
    if "rgbww" in normalized:
        return "rgbww"
    if "rgbw" in normalized:
        return "rgbw"
    if "rgb" in normalized:
        return "rgb"
    if any("rgb" in mode for mode in normalized):
        return "rgb"
    if "hs" in normalized or "xy" in normalized:
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
                        values = [
                            int(hex_value[i : i + 2], 16)
                            for i in range(0, len(hex_value), 2)
                        ]
                    except ValueError:
                        values = []
                else:
                    values = []
            else:
                cleaned = stripped.strip("[]()")
                parts = [segment.strip() for segment in cleaned.split(",") if segment.strip()]
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

    rgb = tuple(max(0, min(255, int(v))) for v in values[:3])
    extras = [max(0, min(255, int(v))) for v in values[3:]]
    return rgb, label, extras


def _resolve_entities(entity_ids):
    lights_with_brightness = []
    lights_without_brightness = []
    switches = []
    missing = []
    unsupported = []

    for entity_id in entity_ids:
        entity = str(entity_id)
        domain = entity.split(".", 1)[0]
        try:
            entity_state = state.get(entity)
        except Exception:  # pragma: no cover - defensive
            entity_state = None

        if entity_state in (None, "unknown", "unavailable"):
            missing.append(entity)
            continue

        if domain == "light":
            try:
                attrs = state.getattr(entity) or {}
            except Exception as err:  # pragma: no cover - defensive logging
                log.warning(
                    "shelves_apply: error retrieving attributes for %s: %s",
                    entity,
                    err,
                )
                attrs = {}

            supported_features = attrs.get("supported_features", 0)
            supported_color_modes = attrs.get("supported_color_modes")
            normalized_modes = _normalize_color_modes(supported_color_modes)

            supports_brightness = False
            if supported_features & 1:
                supports_brightness = True
            if any(
                mode in {"brightness", "hs", "rgb", "rgbw", "rgbww", "xy"}
                or "brightness" in mode
                for mode in normalized_modes
            ):
                supports_brightness = True

            if supports_brightness:
                lights_with_brightness.append(entity)
            else:
                lights_without_brightness.append(entity)
        elif domain == "switch":
            switches.append(entity)
        else:
            unsupported.append(entity)

    return (
        lights_with_brightness,
        lights_without_brightness,
        switches,
        missing,
        unsupported,
    )


def _categorize_color_lights(lights_with_brightness):
    color_capable_lights = []
    brightness_only_lights = []
    color_payload_modes = {}

    for entity_id in lights_with_brightness:
        try:
            entity_attributes = state.getattr(entity_id) or {}
        except Exception as err:  # pragma: no cover - defensive logging
            log.warning(
                "shelves_flash: error retrieving attributes for %s: %s",
                entity_id,
                err,
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

    return color_capable_lights, brightness_only_lights, color_payload_modes


@service
async def shelves_flash(
    targets=None,
    entity_id=None,
    targets_group=None,
    flashes: int = 4,
    on_ms: int = 300,
    off_ms: int = 250,
    brightness: int | None = 230,
    color: str = "red",
    restore: bool = True
):
    """
    Flash shelves; set red on color-capable lights. Snapshots & restores final state (including switches).
    Accepts flexible targeting.
    """
    task.unique("shelves_flash", kill_me=True)

    eids = _normalize_targets(targets=targets, entity_id=entity_id, targets_group=targets_group, **{})
    if not eids:
        log.warning("shelves_flash: no valid targets provided; nothing to do")
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

    (
        lights_with_brightness,
        lights_without_brightness,
        switches,
        missing,
        unsupported,
    ) = _resolve_entities(ids)

    if missing:
        log.warning(
            "shelves_apply_py: skipping unavailable targets: %s", ", ".join(missing)
        )

    if unsupported:
        log.warning(
            "shelves_apply_py: ignoring unsupported domains: %s", ", ".join(unsupported)
        )

    (
        color_capable_lights,
        brightness_only_lights,
        color_payload_modes,
    ) = _categorize_color_lights(lights_with_brightness)

    if not (
        color_capable_lights
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

    if color_capable_lights:
        rgb_payload = []
        rgbw_payload = []
        rgbww_payload = []
        for entity_id in color_capable_lights:
            mode = color_payload_modes.get(entity_id, "rgb")
            if mode == "rgbww":
                rgbww_payload.append(entity_id)
            elif mode == "rgbw":
                rgbw_payload.append(entity_id)
            else:
                rgb_payload.append(entity_id)

        if rgb_payload:
            service.call(
                "light",
                "turn_on",
                entity_id=rgb_payload,
                brightness_pct=brightness_pct_value,
                transition=transition_value,
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
                brightness_pct=brightness_pct_value,
                transition=transition_value,
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
    await shelves_flash(**kw)


@service
async def sonos_ding(
    player: str,
    media_url: str,
    volume: float = 0.35,
    ring_secs: float = 3.0,
    with_group: bool = True
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

    (
        color_capable_lights,
        brightness_only_lights,
        color_payload_modes,
    ) = _categorize_color_lights(lights_with_brightness)

    available = []
    _extend_list(available, color_capable_lights)
    _extend_list(available, brightness_only_lights)
    _extend_list(available, lights_without_brightness)
    _extend_list(available, switches)

    rgb_payload = []
    rgbw_payload = []
    rgbww_payload = []

    if _has_items(color_capable_lights):
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
        if not _has_items(color_capable_lights):
            log.warning(
                "shelves_flash: color '%s' requested but no color-capable lights available; continuing without color",
                color_label,
            )
        elif _has_items(unsupported_color_entities):
            log.info(
                "shelves_flash: color '%s' requested but unsupported by: %s",
                color_label,
                ", ".join(unsupported_color_entities),
            )

        if _has_items(color_capable_lights):
            for entity_id in color_capable_lights:
                mode = color_payload_modes.get(entity_id, "rgb")
                payload_key = "rgb_color"
                payload = _copy_rgb(rgb_color)
                if mode == "rgbww":
                    payload_key = "rgbww_color"
                    payload.append(_extra_channel(extra_channels, 0))
                    payload.append(_extra_channel(extra_channels, 1))
                elif mode == "rgbw":
                    payload_key = "rgbw_color"
                    payload.append(_extra_channel(extra_channels, 0))
                log.info(
                    "shelves_flash: using %s %s for %s",
                    payload_key,
                    payload,
                    entity_id,
                )

    if not _has_items(available):
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
        if _has_items(color_capable_lights):
            if _has_items(rgb_payload):
                service.call(
                    "light",
                    "turn_on",
                    entity_id=rgb_payload,
                    brightness=brightness,
                    rgb_color=_copy_rgb(rgb_color),
                )

            if _has_items(rgbw_payload):
                rgbw_color = _copy_rgb(rgb_color)
                rgbw_color.append(_extra_channel(extra_channels, 0))
                service.call(
                    "light",
                    "turn_on",
                    entity_id=rgbw_payload,
                    brightness=brightness,
                    rgbw_color=rgbw_color,
                )

            if _has_items(rgbww_payload):
                rgbww_color = _copy_rgb(rgb_color)
                rgbww_color.append(_extra_channel(extra_channels, 0))
                rgbww_color.append(_extra_channel(extra_channels, 1))
                service.call(
                    "light",
                    "turn_on",
                    entity_id=rgbww_payload,
                    brightness=brightness,
                    rgbww_color=rgbww_color,
                )
        if _has_items(brightness_only_lights):
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
        if _has_items(lights_without_brightness):
            service.call("light", "turn_on", entity_id=lights_without_brightness)
        if _has_items(switches):
            service.call("switch", "turn_on", entity_id=switches)

        await task.sleep(on_s)

        all_lights = []
        _extend_list(all_lights, color_capable_lights)
        _extend_list(all_lights, brightness_only_lights)
        _extend_list(all_lights, lights_without_brightness)
        if _has_items(all_lights):
            service.call("light", "turn_off", entity_id=all_lights)
        if _has_items(switches):
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
async def doorbell_ring(
    # shelves args
    entity_id=None, targets=None, targets_group=None,
    flashes: int = 4, on_ms: int = 300, off_ms: int = 250, brightness: int | None = 230, color: str = "red", restore: bool = True,
    # sonos args
    player: str | None = None, media_url: str | None = None, volume: float = 0.35, ring_secs: float = 3.0, with_group: bool = True
):
    wait_value = _parse_duration(wait_s)
    log.info(
        "Stub sonos_ding: player=%s volume=%s media_url=%s wait_s=%s",
        player,
        volume,
        media_url,
        wait_value,
    )

