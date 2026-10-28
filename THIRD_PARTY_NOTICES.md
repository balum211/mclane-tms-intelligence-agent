# Third-party notices

The spec-driven development workflows and templates in this repository are vendored from
[alphinside/sdd-adk-antigravity-starter](https://github.com/alphinside/sdd-adk-antigravity-starter)
(commit `462432b6c8b0c39003402666b8848bb8093ca536`), the starter used by the Google codelab
"Spec-Driven ADK Agent Development with Antigravity and Spec-kit". They are licensed under the Apache
License 2.0 (copy in `third_party/sdd-adk-antigravity-starter/LICENSE`) and derive from
[github/spec-kit](https://github.com/github/spec-kit) (MIT).

Vendored, unmodified:
- `.agents/workflows/speckit.*.md` (Antigravity slash commands `/speckit.*`)
- `.specify/templates/*.md`
- `.specify/scripts/bash/*.sh`

Vendored with changes (frontmatter `name` / `description` added so Antigravity loads them; the
Toolbox skill gained a section on AlloyDB and BigQuery sources):
- `.agents/skills/repo-research/SKILL.md`
- `.agents/skills/mcp-toolbox-postgres/SKILL.md`

Adapted from the starter: `server.py`, the `.env.example` layout, `tools.yaml` format and
`antigravity/mcp_config.example.json`.

Written for this project: `.specify/memory/constitution.md`, `specs/001-tms-intelligence/*`,
`specs/002-mclane-delivery-signals/*`, `.agents/rules/*` (in the starter's project-context format),
and the other `.agents/skills/*`.
