# ADR 0002: Entity & script naming convention

- **Status:** Accepted
- **Date:** 2025-09-07
- **Related Issues:** #2

## Context
Consistent names make YAML readable and grep-able across packages, scripts, and automations.

## Decision
Use lowercase snake_case with clear prefixes:
- Entities: media_player.kitchen, media_player.family_room
- Scripts: script.tv_in_kitchen, script.shelves_doorbell_flash
- Helpers: input_boolean.*, input_number.*
- Files: one feature per file under home-assistant/packages/ (e.g., sonos.yaml, ing.yaml)

## Consequences
- Easier cross-references and refactors
- Avoids name collisions
- Requires renaming legacy items to conform

## Alternatives Considered
1) Mixed styles (camelCase/kebab) — inconsistent in HA
2) Long hierarchical names — verbose with little benefit
