# \# Briggs Home Automation Project

# 

# This repository contains my Home Assistant configuration and related automation scripts.

# It is the single source of truth for my smart home setup, including Sonos, Shelly RGBW2,

# Ring, Lutron, Google Assistant, and custom YAML automations.

# 

# \## Structure

# 

home-assistant/

configuration.yaml # main HA config

packages/ # individual packages (Sonos, Ring, Shelves, etc.)

scripts/ # HA scripts

automations/ # HA automations



docs/

ADR/ # Architectural Decision Records (why certain choices were made)

KNOWN-PITFALLS.md # mistakes \& lessons learned



CHANGELOG.md # running log of change





\## Goals



\- Reliable, reproducible smart home configuration  

\- Clear YAML organization with headers in each file  

\- Guard-rails to avoid repeating mistakes  

\- Easy collaboration with ChatGPT for fixes and new features  



\## Workflow



\- Open an \*\*Issue\*\* for bugs or new features  

\- Link Issues to Pull Requests  

\- Keep `CHANGELOG.md` updated  

\- Document decisions in `docs/ADR/`  



\## Environment



\- Home Assistant Core 2025.8.3 (Container)  

\- Raspberry Pi 4 running Docker  

\- Sonos S2 16.2  

\- Lutron Caseta Pro Bridge  

\- Shelly RGBW2 (static IP)  

\- Ring Doorbell  

\- Google Assistant via Nabu Casa  

## Quick Access Links

### Core Docs
- [KICKOFF.md](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/KICKOFF.md)
- [ASSISTANT_CONTEXT.md](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/docs/ASSISTANT_CONTEXT.md)
- [KNOWN-PITFALLS.md](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/docs/KNOWN-PITFALLS.md)

### Home Assistant Packages
- [sonos.yaml](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/home-assistant/packages/sonos.yaml)
- [ring.yaml](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/home-assistant/packages/ring.yaml)
- [shelves.yaml](https://raw.githubusercontent.com/briggswilloughby/briggs-home-automation/main/home-assistant/packages/shelves.yaml)

# Briggs Home Automation Project






