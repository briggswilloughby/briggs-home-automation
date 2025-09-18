# Pico Remote Specification Needs

The Kitchen and Cubbies Pico notes you provided (center button toggle, outer
buttons drive brightness/volume, inner buttons change modes) fully cover the
intent mapping. To finish wiring the remotes into the rebuilt automation layer,
please gather the additional items below for each Pico you want enabled.

## Required Per-Remote Inputs

1. **Remote identifier and entity IDs**
   - Exact Lutron Caseta device name plus the `sensor`/`event` entity exposed in
     Home Assistant for button presses.
   - Mounting location so the helper package can scope lighting/scene targets.
2. **Press types to monitor**
   - Whether we should react to single press only or also long-press / double-
     tap events (Caseta surfaces each as a unique event subtype).
3. **Target wrappers or helpers**
   - The script or service each button should call (e.g., `script.tv_plus_kitchen`,
     `script.cubbies_next_mode`, `script.sonos_volume_up_all`).
   - Note if multiple services need to fire per button (lights plus audio).
4. **Rate limiting / safety**
   - Any debounce rules beyond ADR-0004 so we do not saturate Shelly/Sonos with
     rapid repeats.
   - Expectations for keeping Google Assistant and Pico behavior mirrored.
5. **Default step sizes**
   - Confirm brightness and volume deltas (defaults are ±10%). Call out any room
     that should use a different step so we can encode it once.

## Optional Enhancements

- Time-of-day or occupancy adjustments that should modify button behavior.
- Fail-safe actions if the targeted light group or Sonos player is unavailable.
- Whether button LEDs (if present) should reflect the current cubby mode or
  Sonos grouping state.
