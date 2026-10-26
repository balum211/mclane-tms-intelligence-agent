# Antigravity assets

| Path | What it is | Codelab |
|---|---|---|
| [PROMPTS.md](PROMPTS.md) | Ordered, ready-to-paste prompts. Track A runs and demos this repo; Track B rebuilds it spec-first | Getting Started, Building with Antigravity, Spec-Driven ADK + Spec-kit, Beyond vibe coding |
| `../AGENTS.md` | Repo rules for any coding agent | Building with Antigravity |
| `../.agents/rules/project-context.md` | Always-on workspace rule | Building with Antigravity |
| `../.agents/workflows/speckit.*.md` | spec-kit slash commands (`/speckit.constitution` … `/speckit.implement`), vendored from `alphinside/sdd-adk-antigravity-starter` (Apache-2.0) | Spec-Driven ADK + Spec-kit |
| `../.specify/` | Constitution, templates and helper scripts for spec-kit | Spec-Driven ADK + Spec-kit |
| `../specs/001-tms-intelligence/` | The spec, plan, research, data model, tasks and quickstart this code implements | Spec-Driven ADK + Spec-kit |
| `../.agents/skills/` | Workspace skills (below) | Antigravity Skills |

## Skills

| Skill | Use it for | Bundled |
|---|---|---|
| `tms-sql-analyst` | Data questions, KPI checks, writing SQL for the TMS schema | `scripts/query.py` (guarded), schema cheat sheet, verified examples |
| `freight-invoice-audit` | Overbilling questions, auditing one invoice or a PDF, changing audit rules | `scripts/audit.py` |
| `tms-synthetic-data` | Generating, loading or extending the TMW-style dataset | |
| `adk-tool-author` | Adding a tool or specialist agent the project way | |
| `adk-agent-deploy` | Agent Engine / Cloud Run deployment and Gemini Enterprise registration | |

Skills load on demand: Antigravity reads each skill's `description` and opens the full `SKILL.md`
only when a prompt matches. Mentioning the skill by name in a prompt makes the match certain.
