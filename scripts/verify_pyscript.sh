#!/usr/bin/env bash
set -euo pipefail

HA_CONTAINER=${HA_CONTAINER:-homeassistant}
CONFIG_PATH=${CONFIG_PATH:-/config}
APPS_DIR=${APPS_DIR:-${CONFIG_PATH}/pyscript/apps}
APPS_MAP=${APPS_MAP:-${CONFIG_PATH}/pyscript/apps.yaml}
LOG_FILE=${LOG_FILE:-${CONFIG_PATH}/pyscript/logs/pyscript.log}

step() {
    printf '\n▶ %s\n' "$1"
}

step "Confirming Pyscript apps mapping"
docker exec "$HA_CONTAINER" bash -c "test -d '$APPS_DIR' && test -f '$APPS_MAP'"

docker exec "$HA_CONTAINER" bash -c "python - <<'PY'
import pathlib, sys
apps_dir = pathlib.Path(r'${APPS_DIR}')
apps_map = pathlib.Path(r'${APPS_MAP}')
missing = []
if not apps_map.exists():
    sys.exit('apps.yaml not found')
for raw in apps_map.read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith('#'):
        continue
    if line.endswith(':') and not line.startswith(('module', '-')):
        continue
    if line.startswith('module:'):
        module = line.split(':', 1)[1].strip()
        module_path = apps_dir / f"{module}.py"
        if not module_path.exists():
            missing.append(module_path)
if missing:
    print('Missing module files:')
    for path in missing:
        print(f'  - {path}')
    sys.exit(1)
PY"

step "Checking configuration.yaml includes pyscript apps map"
DOCKER_CMD="grep -E '^\\s*apps:\\s*!include\\s+pyscript/apps.yaml' '$CONFIG_PATH/configuration.yaml'"
docker exec "$HA_CONTAINER" bash -c "$DOCKER_CMD" >/dev/null

step "Ensuring Pyscript apps avoid direct imports"
docker exec "$HA_CONTAINER" bash -c "python - <<'PY'"
import pathlib, re, sys
apps_dir = pathlib.Path(r'${APPS_DIR}')
pattern = re.compile(r'^\s*(from|import)\s+')
violations = []
for path in sorted(apps_dir.glob('*.py')):
    if path.name == '__init__.py':
        continue
    try:
        lines = path.read_text().splitlines()
    except Exception as exc:  # noqa: BLE001
        violations.append(f"{path}: unable to read ({exc})")
        continue
    for idx, line in enumerate(lines, 1):
        if pattern.match(line):
            violations.append(f"{path}:{idx}:{line.strip()}")
if violations:
    print('Direct imports detected:')
    for item in violations:
        print(f'  - {item}')
    sys.exit(1)
PY"

step "Showing recent Pyscript log lines"
docker exec "$HA_CONTAINER" bash -c "if [ -f '$LOG_FILE' ]; then tail -n 40 '$LOG_FILE'; else echo 'Pyscript log not found at $LOG_FILE' >&2; exit 1; fi"

step "All checks completed"
