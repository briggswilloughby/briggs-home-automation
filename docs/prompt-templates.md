# Prompt Templates

This file collects reusable prompt templates to guide collaboration between **Management** and **Implementation** tracks, and to ensure consistent quality when generating or fixing YAML, scripts, and automations.

---

## 🟢 YAML Fix Template (Full Version)

You are my HA/YAML expert. I will paste my complete current file.

Step 1: Diagnose what’s wrong — explain likely causes of the issue. Don’t fix yet.
Step 2: Propose how to fix it — include design notes, trade-offs, and why your change solves the problem.
Step 3: Output the complete corrected file, file-ready (so I can drop it in directly).

Constraints:

[List state/attributes that must be preserved].

Observed behavior: [paste what happened].

Expected behavior: [paste what should happen].

Extra: If possible, explain how I can debug this (logs, Developer Tools, entity states) to confirm it works.

yaml
Copy code

---

## 🟡 YAML Fix Template (Quick Version)

You are my HA/YAML expert. Here’s my file.

Diagnose the issue.

Propose the fix (design notes).

Output the full corrected file.
Constraints: [state what must persist].

yaml
Copy code

---

## 🔄 Sync Prompts

### Management → Implementation

Syncing from Management chat. We are in Phase 1: basic functionality. Current work items: Seahawks flash (Shelly LEDs), Ring ding → LED + Sonos notice, cubby controls, Pico remotes, and Google Home voice control. Use the YAML Fix Template workflow: diagnose, propose, output full file. Deliver file-ready code/snippets to drop into the repo.

shell
Copy code

### Implementation → Management

Syncing from Implementation chat. We just worked on [X file / automation]. Please update the roadmap/work items in Phase 1 accordingly.

yaml
Copy code

---

## 📌 Usage Notes
- Always paste the **full file** when asking for fixes.  
- Explicitly state **Observed vs Expected behavior**.  
- Use **Management → Implementation sync** to pass roadmap updates into Implementation.  
- Use **Implementation → Management sync** to pass delivered work back into the roadmap.  
- Expect file-ready YAML/scripts, not snippets.  

---