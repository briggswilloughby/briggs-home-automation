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

@service
async def shelves_doorbell_flash_py(**kw):
    # wrapper for existing YAML calls
    await shelves_flash(**kw)

@service
async def shelves_flash(
    targets=None,
    flashes: int = 3,
    brightness: int = 230,
    on_ms: int = 200,
    off_ms: int = 200,
):
    ids = _normalize_targets(targets)
    if not ids:
        log.warning("shelves_flash: no targets provided")
        return

    # clamp/convert inputs
    flashes = max(1, int(flashes))
    brightness = max(1, min(255, int(brightness)))
    on_s = max(0.05, float(on_ms) / 1000.0)
    off_s = max(0.05, float(off_ms) / 1000.0)

    # ensure only one flasher runs at a time
    await task.unique("shelves_flash", kill_me=True)

    available = []
    missing = []
    for entity_id in ids:
        try:
            entity_state = state.get(entity_id)
        except (NameError, KeyError):
            entity_state = None
        except Exception as err:  # pragma: no cover - defensive logging
            log.warning(
                "shelves_flash: error retrieving state for %s: %s", entity_id, err
            )
            entity_state = None

        if entity_state is None:
            missing.append(entity_id)
            continue

        available.append(entity_id)

    if missing:
        log.warning("shelves_flash: skipping unavailable targets: %s", ", ".join(missing))

    if not available:
        log.error("shelves_flash: no usable targets after filtering unavailable entities")
        raise ValueError("shelves_flash: no usable targets")

    for i in range(flashes):
        # turn on (brightness optional; remove if your lights are on/off only)
        service.call("light", "turn_on", entity_id=available, brightness=brightness)
        await task.sleep(on_s)
        service.call("light", "turn_off", entity_id=available)
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
