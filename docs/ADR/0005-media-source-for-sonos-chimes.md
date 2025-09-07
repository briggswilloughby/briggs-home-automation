# ADR 0005: Use Media Source URIs for Sonos chimes

- **Status:** Accepted
- **Date:** 2025-09-07
- **Related Issues:** #5

## Context
Direct /local/ URLs sometimes failed MIME detection for Sonos.

## Decision
Use media_player.play_media with **Media Source URIs**:
media-source://media_source/local/dingdong.mp3
Keep chime files under /config/www/ (served as /local/).

## Consequences
- Correct MIME served by HA → reliable Sonos playback
- Keeps assets versioned inside repo

## Alternatives Considered
1) Direct HTTP URLs — flaky MIME/availability
2) TTS for chimes — slower, less controllable
