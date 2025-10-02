# Pyscript app: doorbell services (apps mode)
# - shelves_doorbell_flash_py: wrapper your YAML calls use
# - shelves_flash: real flasher (turn_on / turn_off with delays)
# - sonos_doorbell_chime_py / sonos_ding: stub chime you can expand later
#
# NOTE: Do not import helpers; Pyscript injects @service, log, task, service, etc.

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

    available = (
        lights_with_brightness
        + lights_without_brightness
        + switches
    )

    if not available:
        log.error("shelves_flash: no usable targets after filtering unavailable entities")
        raise ValueError("shelves_flash: no usable targets")

    for i in range(flashes):
        if lights_with_brightness:
            service.call(
                "light",
                "turn_on",
                entity_id=lights_with_brightness,
                brightness=brightness,
            )
        if lights_without_brightness:
            service.call("light", "turn_on", entity_id=lights_without_brightness)
        if switches:
            service.call("switch", "turn_on", entity_id=switches)

        await task.sleep(on_s)

        all_lights = lights_with_brightness + lights_without_brightness
        if all_lights:
            service.call("light", "turn_off", entity_id=all_lights)
        if switches:
            service.call("switch", "turn_off", entity_id=switches)
        if i < flashes - 1:
            await task.sleep(off_s)

@service
async def sonos_doorbell_chime_py(**kw):
    # wrapper for existing YAML calls
    await sonos_ding(**kw)

@service
async def sonos_ding(player: str | None = None, volume: float = 0.15):
    # stub: swap in real chime logic when ready
    log.info("Stub sonos_ding: player=%s volume=%s", player, volume)
