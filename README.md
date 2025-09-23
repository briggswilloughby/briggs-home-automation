# Briggs Home Automation Project

[![Kickoff](https://img.shields.io/badge/KICKOFF.md-blue)](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/KICKOFF.md)
[![Context](https://img.shields.io/badge/ASSISTANT__CONTEXT.md-brightgreen)](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/docs/ASSISTANT_CONTEXT.md)
[![Pitfalls](https://img.shields.io/badge/KNOWN__PITFALLS.md-orange)](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/docs/KNOWN-PITFALLS.md)
[![Changelog](https://img.shields.io/badge/CHANGELOG.md-yellow)](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/CHANGELOG.md)

This repository contains my Home Assistant configuration and related automation scripts. It is the single source of truth for my smart home setup, including Sonos, Shelly RGBW2, Ring, Lutron, Google Assistant, and custom YAML automations.

## Structure

- `home-assistant/`
  - `configuration.yaml`: main Home Assistant configuration
  - `packages/`: individual packages (Sonos, Ring, Shelly, etc.)
  - `scripts/`: reusable Home Assistant scripts
  - `automations/`: Home Assistant automations
- `docs/`
  - `ADR/`: Architectural Decision Records documenting why certain choices were made
  - `KNOWN-PITFALLS.md`: mistakes and lessons learned
- `CHANGELOG.md`: running log of changes

## Goals

- Reliable, reproducible smart home configuration
- Clear YAML organization with headers in each file
- Guard-rails to avoid repeating mistakes
- Easy collaboration with ChatGPT for fixes and new features

## Workflow

- Open an **Issue** for bugs or new features
- Link Issues to Pull Requests
- Keep `CHANGELOG.md` updated
- Document decisions in `docs/ADR/`

## Environment

- Home Assistant Core 2025.8.3 (Container)
- Raspberry Pi 4 running Docker
- Sonos S2 16.2
- Lutron Caseta Pro Bridge
- Shelly RGBW2 (static IP)
- Ring Doorbell
- Google Assistant via Nabu Casa

## Quick Access Links

### Core Docs

- [KICKOFF.md](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/KICKOFF.md)
- [ASSISTANT_CONTEXT.md](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/docs/ASSISTANT_CONTEXT.md)
- [KNOWN-PITFALLS.md](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/docs/KNOWN-PITFALLS.md)

### Home Assistant Packages

- [sonos.yaml](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/home-assistant/packages/sonos.yaml)
