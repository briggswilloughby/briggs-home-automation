# ASSISTANT CONTEXT (Briggs Home Automation)

## Environment (source of truth)
- Home Assistant Core 2025.8.3 (Container)
- Raspberry Pi 4, Docker
- Sonos S2 16.2
- Lutron Caseta Pro Bridge
- Shelly RGBW2 (static IP), Ring Doorbell, Google Assistant via Nabu Casa

## Rules of Engagement (do-not-drift)
1) Only use **currently available** HA services/actions. If uncertain, verify via *Developer Tools → Actions*; never invent services.
2) Prefer **file-ready** YAML with the standard header and zero placeholders.
3) Respect ADRs and Known Pitfalls. If a request conflicts, STOP and surface the conflict.
4) Use explicit volume baselines (ADR-0003).
5) Sonos snapshot/restore **with_group: true** (ADR-0001).
6) Ring ding: trigger on `event.front_door_ding` with `event_type: ding`, `mode: single`, ~4s absorb delay (ADR-0004).
7) Chimes: use **Media Source URI** for `play_media` (ADR-0005).
8) Naming: lowercase snake_case, scripts `script.*`, helpers `input_*` (ADR-0002).

## File layout
- `ha/config/packages/*.yaml` (one feature per file)
- `docs/ADR/*.md`, `docs/KNOWN-PITFALLS.md`, `CHANGELOG.md`

## Output quality bar
- Provide minimal diff OR full replacement file (your call), but always runnable.
- Include acceptance criteria + quick test steps when relevant.

## Retrieval rules
- Always read the **latest** committed file from `main` via raw.githubusercontent.com before proposing edits.
- If the user says “use <commit>”, use that exact commit SHA in the raw URL.
- Never rely on stale chat snippets if a canonical file exists in the repo.

## Output rules
- Produce **complete, file-ready YAML** (not diffs).
- Preserve headers & comments; keep idempotent behavior.
- Respect `.yamllint` (2-space indents; allow up to one blank line) and HA `check_config`.

## Pre-flight checklist (Implementation)
- Confirm file paths and entity ids exist.
- Call out cross-file impacts (helpers, blueprints, scenes, secrets).
- Note rate limits or integration quirks (Sonos snapshots, Ring throttling, Shelly availability, Lutron certs).
- Suggest tests + rollback steps.
