# Antigravity assets

| Path | What it is | Codelab |
|---|---|---|
| [PROMPTS.md](PROMPTS.md) | Ordered, ready-to-paste prompts. Track A runs and demos this repo; Track B rebuilds it spec-first | Getting Started, Building with Antigravity, Spec-Driven ADK + Spec-kit, Beyond vibe coding |
| `../AGENTS.md` | Repo rules for any coding agent | Building with Antigravity |
| `../.agents/rules/project-context.md` | Always-on workspace rule | Building with Antigravity |
| `../.agents/workflows/speckit.*.md` | spec-kit slash commands (`/speckit.constitution` … `/speckit.implement`), vendored from `alphinside/sdd-adk-antigravity-starter` (Apache-2.0) | Spec-Driven ADK + Spec-kit |
| `../.specify/` | Constitution, templates and helper scripts for spec-kit | Spec-Driven ADK + Spec-kit |
| `../specs/001-tms-intelligence/`, `../specs/002-mclane-delivery-signals/` | The specs, plans, research, data models, tasks and quickstarts this code implements | Spec-Driven ADK + Spec-kit |
| [mcp_config.example.json](mcp_config.example.json) | ADK docs MCP server (`mcpdoc` over `https://adk.dev/llms.txt`). Merge into `$HOME/.gemini/config/mcp_config.json` | Spec-Driven ADK + Spec-kit |
| `../tools.yaml` | MCP Toolbox for Databases tools (AlloyDB + BigQuery, read-only), starter format | Spec-Driven ADK + Spec-kit |
| `../server.py`, `../pyproject.toml`, `../uv.lock` | `uv sync`, `uv run adk web .`, `uv run python server.py` exactly as in the starter | Spec-Driven ADK + Spec-kit |
| `../scripts/install_into_sdd_starter.sh` | Copies this agent into your clone of the starter (sdd-adk-agents-agy) without overwriting its files | Spec-Driven ADK + Spec-kit |
| `../.agents/skills/` | Workspace skills (below) | Antigravity Skills |

## Skills

| Skill | Use it for | Bundled |
|---|---|---|
| `tms-sql-analyst` | Data questions, KPI checks, writing SQL for the TMS schema | `scripts/query.py` (guarded), schema cheat sheet, verified examples |
| `freight-invoice-audit` | Overbilling questions, auditing one invoice or a PDF, changing audit rules | `scripts/audit.py` |
| `tms-synthetic-data` | Generating, loading or extending the TMW-style dataset | |
| `adk-tool-author` | Adding a tool or specialist agent the project way | |
| `adk-agent-deploy` | Agent Engine / Cloud Run deployment and Gemini Enterprise registration | |
| `mclane-delivery-signals` | Retail vs Restaurant OTD, dwell time change, geofences / geocodes, load tracking, PC*MILER miles, out-of-route | `scripts/signals.py` (`otd`, `dwell`, `geofence`, `track`, `pcmiler`, `oor`) |
| `repo-research` | Filling in `.agents/rules/project-context.md` from the code (vendored from the codelab starter) | `references/` template |
| `mcp-toolbox-postgres` | Writing `tools.yaml` for MCP Toolbox (Postgres, AlloyDB, BigQuery sources; vendored from the starter) | |

Workspace skills live in `.agents/skills/<name>/SKILL.md` (frontmatter `name` must match the folder,
`description` is required). To use one in every workspace, copy its folder to `~/.gemini/config/skills/`.

Skills load on demand: Antigravity reads each skill's `description` and opens the full `SKILL.md`
only when a prompt matches. Mentioning the skill by name in a prompt makes the match certain.
