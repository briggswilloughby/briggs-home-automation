# ADR 0006: YAML header standard

- **Status:** Accepted
- **Date:** 2025-09-07
- **Related Issues:** #6

## Context
We need every file to be self-describing and traceable to issues/decisions.

## Decision
Every packages/*.yaml begins with:


=============================================================================
PACKAGE: <filename>.yaml
PURPOSE: <what this file does>
ISSUE: #<issue id>
DEPENDS ON: <scripts/entities>
TESTED ON: Home Assistant Core 2025.8.3 (Container), Sonos S2 16.2
NOTES: <extra context>
=============================================================================

## Consequences
- Faster code reviews
- Easier regression tracking
- Slight overhead when creating new files

## Alternatives Considered
1) No headers — context lost
2) PR-only context — not visible in deployed files
