@service
def shelves_doorbell_flash_py(**kw):
    # call the local implementation directly
    return shelves_flash(**kw)

@service
def sonos_doorbell_chime_py(**kw):
    # call the local implementation directly
    return sonos_ding(**kw)

# --- implementations (you can replace these stubs with the real logic) ---
@service
def shelves_flash(targets=None, flashes=3, brightness=230):
    log.info("Stub shelves_flash: targets=%s flashes=%s brightness=%s", targets, flashes, brightness)

@service
def sonos_ding(player=None, volume=0.15):
    log.info("Stub sonos_ding: player=%s volume=%s", player, volume)
