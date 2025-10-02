# Pyscript app: doorbell services (apps mode)
# - shelves_doorbell_flash_py: wrapper your YAML calls use
# - shelves_flash: real flasher (turn_on / turn_off with delays)
# - sonos_doorbell_chime_py / sonos_ding: stub chime you can expand later
#
# NOTE: Do not import helpers; Pyscript injects @service, log, task, service, etc.

import time

DEFAULT_RGB_COLOR = [255, 0, 0]
DEFAULT_COLOR_NAME = "red"

_COLOR_NAME_TO_RGB = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "pink": (255, 192, 203),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "teal": (0, 128, 128),
    "white": (255, 255, 255),
    "warm_white": (255, 244, 229),
    "cool_white": (204, 255, 255),
}

def _normalize_targets(targets):
    if not targets:
        return []
    if isinstance(targets, str):
        # allow "light.a, light.b"
        return [e.strip() for e in targets.split(",") if e.strip()]
    if isinstance(targets, (list, tuple, set)):
        return [str(e) for e in targets]
    return [str(targets)]


def _get_entity_details(entity_id):
    try:
        details = state.get(entity_id, attribute="all")
    except (NameError, KeyError):
        details = None
    except Exception as err:  # pragma: no cover - defensive logging
        log.warning("shelves_flash: error retrieving state for %s: %s", entity_id, err)
        details = None

    if not details:
        try:
            current_state = state.get(entity_id)
        except (NameError, KeyError):
            current_state = None
        except Exception as err:  # pragma: no cover - defensive logging
            log.warning(
                "shelves_flash: error retrieving state for %s: %s", entity_id, err
            )
            current_state = None
        return current_state, {}

    if isinstance(details, dict):
        return details.get("state"), details.get("attributes", {}) or {}

    return details, {}


def _supports_brightness(attributes):
    if not isinstance(attributes, dict):
        return False

    supported_color_modes = attributes.get("supported_color_modes")
    if isinstance(supported_color_modes, (list, tuple, set)):
        for mode in supported_color_modes:
            if mode and str(mode).lower() != "onoff":
                return True
        return False

    supported_features = attributes.get("supported_features")
    if isinstance(supported_features, int):
        return bool(supported_features & 1)

    return attributes.get("brightness") is not None


def _resolve_entities(entity_ids):
    queue = list(entity_ids)
    lights_with_brightness = []
    lights_without_brightness = []
    switches = []
    missing = []
    missing_seen = set()
    unsupported = []
    unsupported_seen = set()
    seen_entities = set()
    seen_groups = set()

    while queue:
        entity_id = queue.pop(0)
        if not entity_id:
            continue

        domain, _, _ = entity_id.partition(".")
        domain = domain.lower()

        if domain == "group":
            if entity_id in seen_groups:
                continue
            seen_groups.add(entity_id)
            state_value, attributes = _get_entity_details(entity_id)
            if state_value is None:
                if entity_id not in missing_seen:
                    missing.append(entity_id)
                    missing_seen.add(entity_id)
                continue
            members = attributes.get("entity_id") or attributes.get("entity_ids") or []
            queue.extend(_normalize_targets(members))
            continue

        if entity_id in seen_entities:
            continue

        state_value, attributes = _get_entity_details(entity_id)
        if state_value is None or str(state_value).lower() in {"unavailable", "unknown"}:
            if entity_id not in missing_seen:
                missing.append(entity_id)
                missing_seen.add(entity_id)
            continue

        seen_entities.add(entity_id)

        if domain == "light":
            if _supports_brightness(attributes):
                lights_with_brightness.append(entity_id)
            else:
                lights_without_brightness.append(entity_id)
        elif domain == "switch":
            switches.append(entity_id)
        else:
            if entity_id not in unsupported_seen:
                unsupported.append(entity_id)
                unsupported_seen.add(entity_id)

    return (
        lights_with_brightness,
        lights_without_brightness,
        switches,
        missing,
        unsupported,
    )


def _parse_color(color_value):
    if color_value is None:
        return list(DEFAULT_RGB_COLOR), DEFAULT_COLOR_NAME

    if isinstance(color_value, (list, tuple)):
        candidate_parts = list(color_value)
        description = ",".join(str(part) for part in candidate_parts)
    elif isinstance(color_value, str):
        candidate = color_value.strip()
        if not candidate:
            return list(DEFAULT_RGB_COLOR), DEFAULT_COLOR_NAME

        lower_candidate = candidate.lower()
        if lower_candidate in _COLOR_NAME_TO_RGB:
            return list(_COLOR_NAME_TO_RGB[lower_candidate]), lower_candidate

        if candidate.startswith("#"):
            hex_value = candidate[1:]
            try:
                if len(hex_value) == 3:
                    rgb = [int(c * 2, 16) for c in hex_value]
                elif len(hex_value) == 6:
                    rgb = [int(hex_value[i : i + 2], 16) for i in (0, 2, 4)]
                else:
                    raise ValueError
                return [max(0, min(255, component)) for component in rgb], lower_candidate
            except (ValueError, TypeError):
                log.warning(
                    "shelves_flash: unrecognized hex color %r; defaulting to %s",
                    color_value,
                    DEFAULT_COLOR_NAME,
                )
                return list(DEFAULT_RGB_COLOR), DEFAULT_COLOR_NAME

        candidate_parts = candidate.replace(",", " ").split()
        description = ",".join(candidate_parts)
    else:
        log.warning(
            "shelves_flash: unsupported color type %r; defaulting to %s",
            type(color_value),
            DEFAULT_COLOR_NAME,
        )
        return list(DEFAULT_RGB_COLOR), DEFAULT_COLOR_NAME

    if len(candidate_parts) == 3:
        try:
            rgb = [
                max(0, min(255, int(float(part))))
                for part in candidate_parts
            ]
            return rgb, description
        except (TypeError, ValueError):
            pass

    log.warning(
        "shelves_flash: unrecognized color %r; defaulting to %s",
        color_value,
        DEFAULT_COLOR_NAME,
    )
    return list(DEFAULT_RGB_COLOR), DEFAULT_COLOR_NAME

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
    rgb_color, color_label = _parse_color(color)

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
    for entity_id in lights_with_brightness:
        try:
            entity_attributes = state.getattr(entity_id) or {}
        except Exception as err:  # pragma: no cover - defensive logging
            log.warning(
                "shelves_flash: error retrieving attributes for %s: %s", entity_id, err
            )
            entity_attributes = {}

        supported_color_modes = entity_attributes.get("supported_color_modes")
        if isinstance(supported_color_modes, str):
            supported_color_modes = [supported_color_modes]

        supports_color = False
        if isinstance(supported_color_modes, (list, tuple, set)):
            for mode in supported_color_modes:
                if not mode:
                    continue
                mode_str = str(mode).lower()
                if mode_str in {"hs", "rgb", "rgbw", "rgbww", "xy"} or "rgb" in mode_str:
                    supports_color = True
                    break

        if supports_color:
            color_capable_lights.append(entity_id)
        else:
            brightness_only_lights.append(entity_id)

    available = (
        color_capable_lights
        + brightness_only_lights
        + lights_without_brightness
        + switches
    )

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
            service.call(
                "light",
                "turn_on",
                entity_id=color_capable_lights,
                brightness=brightness,
                rgb_color=list(rgb_color),
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
async def sonos_ding(player: str | None = None, volume: float = 0.15):
    # stub: swap in real chime logic when ready
    log.info("Stub sonos_ding: player=%s volume=%s", player, volume)
