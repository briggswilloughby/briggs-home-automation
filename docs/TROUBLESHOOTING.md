# Pyscript Troubleshooting Guide

Use this guide to diagnose and recover from common Pyscript issues in the Briggs Home Assistant deployment.

## Logs

- Tail the runtime log inside the container: `docker exec -it homeassistant tail -f /config/pyscript/logs/pyscript.log`
- When debugging service calls, temporarily raise log level in `configuration.yaml` under `logger:` for `custom_components.pyscript`.
- Capture relevant excerpts and attach them to issues/PRs.

## Common problems & fixes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Services missing from Developer Tools | Module not registered in `pyscript/apps.yaml` or syntax error preventing load | Run `scripts/verify_pyscript.sh` and reload Pyscript Apps. Check Home Assistant notifications for tracebacks. |
| `NameError` / missing helpers | Direct `import` usage or reliance on unavailable globals | Remove imports, rely on injected helpers (`log`, `task`, `service`). Confirm guardrails in `docs/AGENT_ANCHOR.md`. |
| Pyscript reload fails silently | Cached task still running | Use `await task.unique("<name>", kill_me=True)` in long-running services; restart Pyscript from UI if needed. |
| Lighting automations stuck on | Loop terminated early, leaving lights on | Ensure loops balance `turn_on`/`turn_off` even on exceptions. Add `try/finally` cleanup if necessary. |
| Logs full of `Event loop is closed` | Home Assistant restart interrupted running tasks | Restart Home Assistant container. Inspect logs for root cause before bringing automations back online. |

## Escalation checklist

1. Run `scripts/verify_pyscript.sh` and confirm all checks pass.
2. Reload Pyscript Apps from the UI.
3. If errors persist, restart the Home Assistant container (`docker restart homeassistant`).
4. Still failing? Open an issue with:
   - Steps to reproduce
   - Relevant log excerpts
   - Mention of any ADR conflicts or guardrail violations
5. Document the fix in `CHANGELOG.md` once resolved.
