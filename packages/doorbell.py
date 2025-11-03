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


def _is_jinja_undefined(value):
    try:
        return value is not None and getattr(value.__class__, "__name__", "") == "LoggingUndefined"
    except Exception:
        return False


def _safe_str(value, default=""):
    """Return a plain string or default. Protects against Jinja LoggingUndefined."""
    try:
        if value is None or _is_jinja_undefined(value):
            return default
        return str(value)
    except Exception:
        return default


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
                # logging removed to avoid passing template/undefined objects
                attrs = {}

            supported_features = attrs.get("supported_features", 0)
            supported_color_modes = attrs.get("supported_color_modes")
            normalized_modes = _normalize_color_modes(supported_color_modes)

            supports_brightness = False
            for mode in normalized_modes:
                if (
                    mode in {"brightness", "hs", "rgb", "rgbw", "rgbww", "xy"}
                    or "brightness" in mode
                ):
                    supports_brightness = True
                    break

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
            # logging removed to avoid passing template/undefined objects
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
            # guard active; skipping (log removed to avoid potential template serialization issues)
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

    # Await all coroutines explicitly
    pending = []
    for coro in sonos_tasks:
        if coro is not None:
            pending.append(coro)
    for coro in flash_tasks:
        if coro is not None:
            pending.append(coro)

    if not pending:
        # nothing to do (log removed to avoid potential template serialization issues)
        return

    # Ensure all are coroutines before gathering
    await asyncio.gather(*(c for c in pending if hasattr(c, "__await__")))


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
    # Combine all target sources
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
    # Deduplicate
    ids = []
    seen_ids = set()
    for candidate_id in raw_ids:
        if candidate_id not in seen_ids:
            ids.append(candidate_id)
            seen_ids.add(candidate_id)
    # Parse color
    if color is not None:
        rgb_color, color_label, extra_channels = _parse_color(color)
    else:
        parsed_rgbw = _parse_rgbw_values(rgbw)
        rgb_color = tuple(parsed_rgbw[:3])
        extra_channels = parsed_rgbw[3:]
        color_label = f"rgbw {parsed_rgbw[:4]}"
    brightness_pct_value = max(1, min(100, int(brightness_pct or 0)))
    transition_value = max(0.0, float(transition or 0.0))
    # Always treat as RGBW
    rgbw_color = list(rgb_color) + [extra_channels[0] if len(extra_channels) > 0 else 0]
    service.call(
        "light",
        "turn_on",
        entity_id=ids,
        brightness=round(255 * (brightness_pct_value / 100.0)),
        transition=transition_value,
        rgbw_color=rgbw_color,
    )


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
    # Combine all target sources
    raw_ids = []
    for source in (targets, entity_id, targets_group):
        raw_ids.extend(_normalize_targets(source))
    for key in kwargs:
        if isinstance(key, str) and key.startswith(("light.", "switch.", "group.")):
            raw_ids.append(key)
    if not raw_ids:
        raw_ids = list(_DEFAULT_SHELF_TARGETS)
    # Deduplicate
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
    rgb_color, color_label, extra_channels = _parse_color(color)
    await task.unique("shelves_flash", kill_me=True)
    # Snapshot state for restore
    restore_scene_entity = None
    if restore:
        scene_slug = f"shelves_flash_restore_{int(time.time() * 1000)}"
        try:
            service.call(
                "scene",
                "create",
                scene_id=scene_slug,
                snapshot_entities=ids,
            )
            restore_scene_entity = f"scene.{scene_slug}"
        except Exception as err:
            # logging removed to avoid passing template/undefined objects
            pass
            pass
        # Give the backend a short moment to persist the snapshot before flashing
        await task.sleep(0.10)
    # Flash loop
    rgbw_color = list(rgb_color) + [extra_channels[0] if len(extra_channels) > 0 else 0]

    # Split targets into those that support a device 'Flash' effect and the rest.
    effect_entities = []
    non_effect_entities = []
    try:
        for e in ids:
            try:
                attrs = state.getattr(e) or {}
            except Exception:
                attrs = {}
            elist = attrs.get("effect_list") or []
            # effect_list can contain different casings; check case-insensitive
            supports_flash = False
            try:
                for it in elist:
                    if str(it).strip().lower() == "flash":
                        supports_flash = True
                        break
            except Exception:
                supports_flash = False

            if supports_flash:
                effect_entities.append(e)
            else:
                non_effect_entities.append(e)
    except Exception:
        # if anything goes wrong, fall back to original behaviour
        effect_entities = []
        non_effect_entities = list(ids)

    for i in range(flashes_value):
        # Turn on effect-capable lights using their built-in effect (more reliable on Shelly)
        if effect_entities:
            try:
                service.call(
                    "light",
                    "turn_on",
                    entity_id=effect_entities,
                    effect="Flash",
                    brightness=brightness_value,
                    rgbw_color=rgbw_color,
                )
            except Exception:
                # ignore failures here; we'll still try the non-effect path
                pass

        # Turn on non-effect lights with the RGBW/brightness payload
        if non_effect_entities:
            try:
                service.call(
                    "light",
                    "turn_on",
                    entity_id=non_effect_entities,
                    brightness=brightness_value,
                    rgbw_color=rgbw_color,
                )
            except Exception:
                pass

        await task.sleep(on_s)

        # Turn everything off between flashes
        if effect_entities:
            try:
                service.call(
                    "light",
                    "turn_off",
                    entity_id=effect_entities,
                )
            except Exception:
                pass
        if non_effect_entities:
            try:
                service.call(
                    "light",
                    "turn_off",
                    entity_id=non_effect_entities,
                )
            except Exception:
                pass

        if i < flashes_value - 1:
            await task.sleep(off_s)
    # Restore state
    if restore and restore_scene_entity:
        try:
            service.call("scene", "turn_on", entity_id=restore_scene_entity)
        except Exception as err:
            # logging removed to avoid passing template/undefined objects
            pass
        # Allow devices time to report restored state, then nudge updates
        await task.sleep(0.25)
        for e in ids:
            try:
                service.call("homeassistant", "update_entity", entity_id=e)
            except Exception:
                pass
@service
async def sonos_doorbell_chime_py(
    player: str | None = None,
    media_url: str | None = None,
    volume: float = 0.3,
    wait_s: float | None = None,
):
    wait_value = _parse_duration(wait_s)
    if not (player and media_url):
        # nothing to do
        return

    # Snapshot simple state (volume + playing state) — best-effort
    try:
        attrs = state.getattr(player) or {}
        prev_volume = attrs.get("volume_level")
    except Exception:
        prev_volume = None
    try:
        prev_state = state.get(player)
    except Exception:
        prev_state = None

    try:
        service.call(
            "media_player",
            "volume_set",
            entity_id=player,
            volume_level=volume,
        )
        service.call(
            "media_player",
            "play_media",
            entity_id=player,
            media_content_id=_safe_str(media_url, ""),
            media_content_type="music",
        )
    except Exception:
        # avoid raising errors from media calls
        pass

    if wait_value:
        await task.sleep(wait_value)

    # Restore previous volume and attempt to resume playback if it was playing
    try:
        if prev_volume is not None:
            service.call(
                "media_player",
                "volume_set",
                entity_id=player,
                volume_level=float(prev_volume),
            )
        if prev_state == "playing":
            # Try to resume — best-effort; Sonos may not restore queued media automatically
            service.call("media_player", "media_play", entity_id=player)
    except Exception:
        pass

