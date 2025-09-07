# ADR 0001: Use with_group: true for Sonos snapshot/restore

- **Status:** Accepted
- **Date:** 2025-09-07
- **Related Issues:** #1

---

## Context
Sonos speakers in Home Assistant may be grouped.  
Using media_player.snapshot / media_player.restore without with_group: true fails to restore grouped players correctly.  
This caused prior errors where only the coordinator speaker was restored, leaving grouped speakers silent.

## Decision
Always use with_group: true when snapshotting/restoring Sonos players.

## Consequences
- Ensures consistent restore behavior for grouped playback  
- Slightly slower, since it processes group state as well as the main player  
- Existing scripts must be updated if they omit with_group: true  

## Alternatives Considered
1. Exclude with_group: true  unreliable for groups  
2. Manually ungroup/regroup speakers  brittle and more complex  
