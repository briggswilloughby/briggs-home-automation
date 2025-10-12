# apps mode: no imports from pyscript; helpers are injected: @service, log, task, state, service
import time

# ---------- utilities ----------

def _as_list(x):
    if not x:
        return []
    if isinstance(x, (list, tuple, set)):
        return [str(i).strip() for i in x if str(i).strip()]
    # CSV or single string
    return [s.strip() for s in str(x).split(",") if s.strip()]

def _expand_if_group(eid):
    ent = state.get(eid)
    if not ent:
        return [eid]
    members = ent.get("attributes", {}).get("entity_id")
    if isinstance(members, (list, tuple)):
        return [m for m in members]
    return [eid]

def _entity_exists(eid):
    return state.get(eid) is not None

def _is_available(eid):
    cur = state.get(eid)
    if not cur:
        return False
    st = cur.get("state")
    return st not in ("unavailable", "unknown", None)

def _is_light(eid): return eid.startswith("light.")
def _is_switch(eid): return eid.startswith("switch.")

def _is_color_capable(light_eid):
    attrs = (state.get(light_eid) or {}).get("attributes", {})
    modes = attrs.get("supported_color_modes") or []
    if isinstance(modes, set):
        modes = list(modes)
    modes = [str(m).lower() for m in modes]
    return any(m in modes for m in ("rgb", "rgbw", "rgbww", "xy", "hs"))

def _partition_entities(eids):
    eids = [e for e in eids if _entity_exists(e)]
    avail = [e for e in eids if _is_available(e)]
    skipped = [e for e in eids if e not in avail]
    lights = [e for e in avail if _is_light(e)]
    switches = [e for e in avail if _is_switch(e)]
    color_lights = [e for e in lights if _is_color_capable(e)]
    plain_lights = [e for e in lights if e not in color_lights]
    return color_lights, plain_lights, switches, skipped

def _normalize_targets(**kw):
    # Accept: targets (list/CSV), entity_id (group or entity), targets_group,
    # plus stray top-level ids like light.x: null
    candidates = []
    candidates += _as_list(kw.get("targets"))
    candidates += _as_list(kw.get("entity_id"))
    tg = kw.get("targets_group")
    if tg:
        candidates += _expand_if_group(tg)

    expanded = []
    for eid in candidates:
        expanded += _expand_if_group(eid)

    # tolerate accidental top-level keys like light.shelf_1: null
    for k in list(kw.keys()):
        if isinstance(k, str) and (k.startswith("light.") or k.startswith("switch.") or k.startswith("group.")):
            expanded.append(k)

    # default if nothing provided
    if not expanded and _entity_exists("light.shelves_all"):
        expanded = _expand_if_group("light.shelves_all")

    # filter to light.* and switch.*
    expanded = [e for e in expanded if _is_light(e) or _is_switch(e)]
    # uniq, stable
    seen = set()
    out = []
    for e in expanded:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out

async def _snapshot(scene_id, entities):
    if not entities:
        return
    await service.call("scene", "create", scene_id=scene_id, snapshot_entities=entities)

async def _restore(scene_id):
    await service.call("scene", "turn_on", entity_id=f"scene.{scene_id}")

# ---------- public: shelves_flash ----------

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

    color_l, plain_l, switches, skipped = _partition_entities(eids)
    log.info(f"shelves_flash: targets={len(eids)} -> color_lights={len(color_l)}, plain_lights={len(plain_l)}, switches={len(switches)}, skipped={len(skipped)}")
    if skipped:
        log.warning(f"shelves_flash: skipped unavailable={skipped}")

    # snapshot (include switches too)
    scene_id = f"pyscript_doorbell_snapshot_{int(time.time())}"
    await _snapshot(scene_id, color_l + plain_l + switches)

    # compute kwargs
    on_kwargs_color = {"brightness": int(brightness)} if brightness is not None else {}
    on_kwargs_plain = {"brightness": int(brightness)} if brightness is not None else {}

    # set red preference (+hs fallback; HA ignores unknown keys)
    if color.lower() == "red":
        on_kwargs_color["rgb_color"] = [255, 0, 0]
        on_kwargs_color["hs_color"] = [0, 100]
    else:
        on_kwargs_color["rgb_color"] = [255, 0, 0]
        on_kwargs_color["hs_color"] = [0, 100]

    try:
        for _ in range(int(flashes)):
            # ON pulse
            tasks = []
            if color_l:
                tasks.append(service.call("light", "turn_on", entity_id=color_l, transition=max(on_ms/1000.0 - 0.05, 0), **on_kwargs_color))
            if plain_l:
                tasks.append(service.call("light", "turn_on", entity_id=plain_l, transition=max(on_ms/1000.0 - 0.05, 0), **on_kwargs_plain))
            if switches:
                tasks.append(service.call("switch", "turn_on", entity_id=switches))
            if tasks:
                await task.gather(*tasks)
            await task.sleep(on_ms/1000.0)

            # OFF pulse
            tasks = []
            if color_l or plain_l:
                tasks.append(service.call("light", "turn_off", entity_id=color_l + plain_l, transition=max(off_ms/1000.0 - 0.05, 0)))
            if switches:
                tasks.append(service.call("switch", "turn_off", entity_id=switches))
            if tasks:
                await task.gather(*tasks)
            await task.sleep(off_ms/1000.0)

    finally:
        if restore:
            await _restore(scene_id)
            log.info("shelves_flash: restore done")

# ---------- wrapper for HA callers ----------

@service
async def shelves_doorbell_flash_py(**kw):
    """Stable public wrapper name"""
    await shelves_flash(**kw)

# ---------- Sonos chime ----------

@service
async def sonos_ding(
    player: str,
    media_url: str,
    volume: float = 0.35,
    ring_secs: float = 3.0,
    with_group: bool = True
):
    """
    Snapshot -> set volume -> play media -> sleep -> restore.
    """
    task.unique(f"sonos_ding_{player}", kill_me=True)

    if not player or not media_url:
        log.warning("sonos_ding: player and media_url are required")
        return

    try:
        await service.call("sonos", "snapshot", entity_id=player, with_group=with_group)
        await service.call("media_player", "volume_set", entity_id=player, volume_level=float(volume))
        await service.call("media_player", "play_media", entity_id=player, media_content_id=media_url, media_content_type="music")
        await task.sleep(float(ring_secs))
    finally:
        await service.call("sonos", "restore", entity_id=player, with_group=with_group)

@service
async def sonos_doorbell_chime_py(**kw):
    await sonos_ding(**kw)

# ---------- Orchestrator: ring (flash + chime concurrently) ----------

@service
async def doorbell_ring(
    # shelves args
    entity_id=None, targets=None, targets_group=None,
    flashes: int = 4, on_ms: int = 300, off_ms: int = 250, brightness: int | None = 230, color: str = "red", restore: bool = True,
    # sonos args
    player: str | None = None, media_url: str | None = None, volume: float = 0.35, ring_secs: float = 3.0, with_group: bool = True
):
    """
    Run shelves flash and sonos chime concurrently.
    """
    task.unique("doorbell_ring", kill_me=True)

    tasks = []
    tasks.append(shelves_flash(
        targets=targets, entity_id=entity_id, targets_group=targets_group,
        flashes=flashes, on_ms=on_ms, off_ms=off_ms, brightness=brightness, color=color, restore=restore
    ))
    if player and media_url:
        tasks.append(sonos_ding(player=player, media_url=media_url, volume=volume, ring_secs=ring_secs, with_group=with_group))

    await task.gather(*tasks)

# ---------- quick sanity ----------

@service
async def test_blink(entity_id: str, times: int = 2, on_ms: int = 200, off_ms: int = 200):
    task.unique(f"test_blink_{entity_id}", kill_me=True)
    for _ in range(int(times)):
        if entity_id.startswith("light."):
            await service.call("light", "turn_on", entity_id=entity_id)
            await task.sleep(on_ms/1000.0)
            await service.call("light", "turn_off", entity_id=entity_id)
            await task.sleep(off_ms/1000.0)
        elif entity_id.startswith("switch."):
            await service.call("switch", "turn_on", entity_id=entity_id)
            await task.sleep(on_ms/1000.0)
            await service.call("switch", "turn_off", entity_id=entity_id)
            await task.sleep(off_ms/1000.0)
        else:
            log.warning(f"test_blink: unsupported entity_id={entity_id}")
            break
