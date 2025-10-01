# Pyscript Apps-Mode Anchor

This anchor supplements `docs/ASSISTANT_CONTEXT.md` with guardrails that keep the Home Assistant Pyscript integration operating in apps mode. Treat these as hard requirements whenever you touch anything under `pyscript/`.

## Guardrails

1. **Apps-only layout** – Modules live in `pyscript/apps/` and are registered in `pyscript/apps.yaml`. Do not place runnable code in the package root.
2. **One service per capability** – Expose entry points with `@service` decorators; helpers stay private (`_helper()`). Keep names snake_case to align with ADR-0002.
3. **No direct imports** – Pyscript injects `@service`, `task`, `service`, `log`, etc. Avoid `import`/`from` statements unless absolutely unavoidable (and document the exception in-line).
4. **Async first** – Prefer `async def` services when calling Home Assistant services or waiting on tasks. Use `await task.sleep()` for timing instead of `time.sleep()`.
5. **Idempotent side effects** – Guard long-running work with `await task.unique()` when it should not overlap, and validate inputs before calling Home Assistant services.
6. **Minimal configuration coupling** – Keep entity IDs and helpers defined in YAML packages. Accept them as service kwargs instead of hard-coding when practical.

## Review checklist

Before committing Pyscript changes:

- Confirm every module referenced in `apps.yaml` exists and loads without syntax errors.
- Re-run `scripts/verify_pyscript.sh` (see README) from your workstation and resolve any failures.
- Validate new services show up under **Developer Tools → Actions** and document usage in the CHANGELOG when shipped.
