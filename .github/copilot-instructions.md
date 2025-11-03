## Copilot / AI agent instructions — Briggs Home Automation (Home Assistant)

This file gives targeted guidance so an AI coding agent can be productive immediately in this Home Assistant configuration repo.

Keep answers concise, make small, testable edits, and prefer non-destructive changes (create PRs, keep backups).

1) Big-picture architecture
- This repo is a Home Assistant Core configuration bundle (see `configuration.yaml`).
- Major areas:
  - `packages/` — grouped YAML packages (Sonos, Shelly, Ring, Lutron). Modify these for integrations and entities.
  - `pyscript/` — Python-based automations. Two modes are used: apps-mode under `pyscript/apps` and module/helpers in `pyscript`.
  - `scripts/` and `scripts.yaml` — reusable HA scripts invoked from YAML automations or pyscript.
  - `custom_components/` and `deps/` — local integration code and vendored dependencies.
  - `docs/`, `CHANGELOG.md`, `KICKOFF.md` — design decisions, pitfalls, and operational runbook.

2) Pyscript conventions (high-value, repo-specific)
- Files under `pyscript/apps` are written in "apps mode": they rely on pyscript runtime to inject decorators and helpers (e.g. `@service`, `log`, `state`, `task`). Do NOT add regular Python imports that expect a standard Python package runtime for these files.
- Example: `pyscript/apps/doorbell.py` defines `@service async def doorbell_ring_py(...)` and uses `state.get`, `state.getattr`, and `log`. Mirror these patterns when adding new apps.
- Small helper functions (parsing durations, color handling) are kept in the same file rather than separate modules. Prefer keeping cohesive behavior together unless adding widely reused helpers — then place them under `pyscript/` root and document usage.
- Use defensive lookup patterns: check `state.get(entity)` and handle `None`, `unknown`, and `unavailable` states consistently (see `_resolve_entities`).

3) Important files to reference when making changes
- `configuration.yaml` — global includes and top-level configuration. Keep any changes compatible with the file-based includes used here.
- `packages/` — modify integration-level YAML here.
- `pyscript/apps/doorbell.py` — canonical example of apps-mode style, locking/guarding patterns, and color/brightness handling.
- `pyscript/apps/hello_app.py` — minimal apps-mode example for logging and service exposure.
- `scripts/verify_pyscript.sh` — local validation script to run before deploying changes to a live HA instance. Always run it in the Docker host or within the same environment used for HA.
- `docs/AGENT_ANCHOR.md`, `docs/HA_PYSCRIPT_PLAYBOOK.md` — operational playbooks and rationale; reference them for why some design choices were made.

4) Developer workflows & how-to (commands and quick checks)
- Local validation (preferred): run `scripts/verify_pyscript.sh` inside the same environment/container that runs Home Assistant. It validates app-mode mappings and common errors.
- When editing pyscript apps, prefer small, incremental commits and run YAML linting if available (`.yamllint` exists in this repo root).
- For live debugging: inspect `home-assistant.log` in the repo root (this repo keeps logs as part of backups) and use the `log` statements in pyscript apps for tracing.

5) Patterns and code examples (do this style)
- Normalize inputs early: helpers like `_normalize_targets`, `_parse_duration`, and `_to_float` are used widely in `doorbell.py`. Follow that style (defensive parsing + clear defaults).
- Entity resolution: use a helper that classifies entities into lights with brightness, lights without brightness, switches, missing, unsupported (see `_resolve_entities`).
- Color/brightness payloads: compute a brightness byte from percent using `_pct_to_brightness` and prefer explicit RGB/RGBW/RGBWW payload modes via `_preferred_color_payload_mode`.

6) Integration and external dependencies
- This repo expects Home Assistant Core runtime with the `pyscript` integration enabled. Do not attempt to unit-test pyscript-only helpers outside of an appropriate runtime unless you provide a thin shim for `state`, `log`, `service`, and `task`.
- Sonos and Shelly integrations are configured in `packages/` and may rely on static IPs or device certs in the repo (see `lutron_caseta-*.pem` files). Avoid publishing certificates or credentials.

7) PR and change guidance for AI agents
- Keep changes minimal and localized. If touching `configuration.yaml` or global packages, include a short changelog entry in `CHANGELOG.md` and run `scripts/verify_pyscript.sh`.
- When adding services or scripts, follow naming conventions: pyscript services frequently end with `_py` (e.g. `doorbell_ring_py`, `sonos_doorbell_chime_py`). Use snake_case and include a clear `guard_seconds` parameter when relevant.

8) When you are stuck or need context
- Open `docs/AGENT_ANCHOR.md` and `KICKOFF.md` for project rationale and deployment notes.
- Search for patterns in `pyscript/apps` first — those are the canonical examples.

If any of these files are incomplete or you want extra examples (tests, more validation scripts, or a small shim to run pyscript functions locally), tell me what to add and I will implement it.
