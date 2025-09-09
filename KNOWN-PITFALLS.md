### YAML / Lint
- Indentation is 2 spaces; `yamllint` enforces it. One blank line between sections is OK (`empty-lines: max 1`).
- Duplicate keys silently override; prefer anchors/aliases or split sections clearly.

### HA reloads
- After pushes/pulls, use **Reload packages** (Settings → Developer Tools → YAML).
- If helpers/entities change names, update all references; HA won’t auto-rename.

### Symlinked config
- `~/ha/config/packages` is a symlink to `~/briggs-home-automation/home-assistant/packages`.
- If something breaks, rollback: `rm ~/ha/config/packages && mv ~/ha/config/packages-backup ~/ha/config/packages`.

### Integrations
- **Sonos:** snapshot/restore timing; grouped players can “steal focus”; avoid volume jumps—set defaults.
- **Ring:** cloud throttling; debounce/chime double-ding.
- **Shelly:** devices can drop offline; guard with `availability` / timeouts.
- **Lutron:** cert/keys must be valid; don’t commit keys; network name changes break integrations.

### Secrets & noise
- Never commit `secrets.yaml`, DB files, logs; keep `.gitignore` up to date.
