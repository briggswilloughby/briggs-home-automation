# ADR 0004: Ring doorbell ding handling

- **Status:** Accepted
- **Date:** 2025-09-07
- **Related Issues:** #4

## Context
Using generic events caused duplicate/false triggers and race conditions.

## Decision
- Trigger on event.front_door_ding with event_type: ding
- Use mode: single + **4s absorb delay** to suppress duplicates
- Separate concerns: Pyscript services handle shelves flash (pyscript.shelves_doorbell_flash_py)
  and the Sonos chime (pyscript.sonos_doorbell_chime_py).

## Consequences
- Reliable single action per press
- Clear scripts for re-use and testing
- Slight delay to absorb dupes

## Alternatives Considered
1) Listen to multiple event types — noisy
2) Debounce using helpers — heavier config for same result
