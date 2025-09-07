# ADR 0003: Default volume baselines for scripted playback

- **Status:** Accepted
- **Date:** 2025-09-07
- **Related Issues:** #3

## Context
Ad-hoc volumes caused unexpected loud playback (esp. “TV in Kitchen”).

## Decision
Define explicit baseline volumes in scripts:
- 	v_in_kitchen baseline volume: **0.15**
- Chimes/alerts: 0.20 unless overridden
Store baselines in one place (helpers or variables in sonos.yaml) and reference them.

## Consequences
- Predictable loudness across flows
- One edit updates all consumers
- Slight indirection vs. hardcoding

## Alternatives Considered
1) Per-script hardcoded volumes — drift & surprises
2) Global single volume — too coarse
