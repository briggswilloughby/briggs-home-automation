# Home Assistant Pyscript Daily Ops Playbook

Use this playbook when you update, deploy, or validate the Pyscript apps that live under `/config/pyscript` on the Home Assistant host.

## 1. Prep the repo

1. Pull latest `main` and sync secrets as needed.
2. Edit Python apps in `pyscript/apps/` and update `pyscript/apps.yaml` if new modules are introduced.
3. Update YAML packages or docs that reference the new services.

## 2. Run local checks

1. `yamllint` + `hass --script check_config` (handled by CI, but run locally when touching YAML).
2. Execute `scripts/verify_pyscript.sh` (see below) to confirm the container mapping, configuration include, import guardrail, and that logs are healthy.
3. Commit, push, and open a PR summarizing the change and any new services.

## 3. Deploy on the Home Assistant host

1. `git pull` the repo on the host (usually `/config`).
2. Restart or reload Pyscript apps:
   - Home Assistant UI → **Developer Tools → YAML → Reload Pyscript Apps** (or restart the add-on if reload fails).
3. Watch the Home Assistant **Notifications** panel for load errors.

## 4. Post-deploy validation

1. Confirm new services appear under **Developer Tools → Actions**.
2. Manually trigger critical services (e.g., doorbell flash) to ensure runtime behavior matches expectations.
3. Tail the Pyscript log (see troubleshooting) for warnings or tracebacks.

## Reference: verification script

`scripts/verify_pyscript.sh` expects Docker access and defaults to container `homeassistant` with config mounted at `/config`. Override with environment variables if your setup differs:

```bash
HA_CONTAINER=my-ha ./scripts/verify_pyscript.sh
```

Environment variables:

- `HA_CONTAINER`: name or ID of the running Home Assistant container (default `homeassistant`).
- `CONFIG_PATH`: path to the mounted config directory inside the container (default `/config`).
- `APPS_DIR`: path to the Pyscript apps directory inside the container (default `$CONFIG_PATH/pyscript/apps`).
