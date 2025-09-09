# =============================================================================
# GIT_WORKFLOW.md
# PURPOSE: Define how Git, Issues, and Pull Requests are used in the
#          Briggs Home Automation Project to keep Implementation and Management
#          aligned and prevent drift.
# =============================================================================

## Branching & Commits
- All changes start from `main`.
- Work is committed locally, validated, then pushed to `main` unless otherwise noted.
- Commit messages:
  - Use short, descriptive prefix + context.
  - Examples:
    - `fix: correct YAML header in sonos.yaml`
    - `feat: add cubbies mode aliases`
    - `docs: update ADR 0005 media source decision`
    - `ci: adjust yamllint rules`

## Issues
- Use GitHub Issues to track:
  - Bugs (broken automation, failing CI, unexpected behavior).
  - Enhancements (new automation, new scripts).
  - Chores (refactoring, cleanup, repo tasks).
- Issue template:
  - **Title**: short, action-oriented (e.g., `fix: Ring chime double-trigger`).
  - **Body**:
    - Problem
    - Expected Behavior
    - Actual Behavior
    - Acceptance Criteria
    - Related ADRs / Files

## Pull Requests
- All non-trivial changes should use a PR.
- PR description must include:
  - **Summary** of change.
  - **Related Issues** (e.g., `Closes #12`).
  - **Test Plan** (manual steps or CI checks).
  - **Acceptance Criteria** from the Issue.
- Labels:
  - `fix`, `feat`, `docs`, `chore`, `ci`

## Validation
- All YAML must pass:
  - `yamllint` (lint rules defined in `.yamllint`).
  - `ha core check` (syntax validation for Home Assistant).
- CI will run automatically on push and PR.

## Implementation Thread Instructions
When requesting changes in Implementation:
1. Always reference files from the repo, not pasted copies.
   - Example:  
     > "Update `home-assistant/packages/sonos.yaml` on `main`"
2. Use Issues for bugs/feature requests.
3. Expect Implementation to:
   - Pull the latest from `main`.
   - Propose **file-ready YAML**.
   - Commit & PR changes per this workflow.

## Quick Access
- [KICKOFF.md](./../KICKOFF.md)
- [ASSISTANT_CONTEXT.md](./ASSISTANT_CONTEXT.md)
- [KNOWN-PITFALLS.md](./KNOWN-PITFALLS.md)
- [ADR Folder](./ADR)
