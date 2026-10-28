#!/usr/bin/env bash
# Copy the TMS Intelligence agent into a clone of the codelab starter (sdd-adk-agents-agy), next to
# restaurant_concierge, so both agents show up in `uv run adk web .` and share the spec-kit setup.
#
#   git clone https://github.com/alphinside/sdd-adk-antigravity-starter.git sdd-adk-agents-agy
#   ./scripts/install_into_sdd_starter.sh ../sdd-adk-agents-agy
#
# Nothing in the starter is deleted. Files that would be replaced are backed up as *.bak first.
set -euo pipefail
DEST="${1:?usage: $0 <path-to-sdd-adk-agents-agy>}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
[[ -f "$DEST/pyproject.toml" && -d "$DEST/.agents" ]] || { echo "Not a starter clone: $DEST" >&2; exit 1; }

copy() {  # copy <relative path> without clobbering silently
  local rel="$1"
  if [[ -e "$DEST/$rel" && ! -d "$SRC/$rel" ]]; then cp "$DEST/$rel" "$DEST/$rel.bak"; fi
  mkdir -p "$(dirname "$DEST/$rel")"
  cp -R "$SRC/$rel" "$(dirname "$DEST/$rel")/"
}

for p in tms_agent tms_data tests evals sql specs/001-tms-intelligence specs/002-mclane-delivery-signals \
         data/sample_invoices antigravity docs; do
  copy "$p"
done
for s in "$SRC"/.agents/skills/*/; do
  name="$(basename "$s")"
  [[ -e "$DEST/.agents/skills/$name" ]] && echo "keep starter skill: $name" && continue
  cp -R "$s" "$DEST/.agents/skills/"
done
mkdir -p "$DEST/.agents/rules"
[[ -f "$DEST/.agents/rules/project-context.md" ]] && cp "$DEST/.agents/rules/project-context.md" "$DEST/.agents/rules/project-context.md.bak"
cp "$SRC/.agents/rules/project-context.md" "$DEST/.agents/rules/project-context.md"
cp "$SRC/tools.yaml" "$DEST/tools.tms.yaml"     # the starter keeps its own tools.yaml
cp "$SRC/AGENTS.md" "$DEST/AGENTS.tms.md"
rm -rf "$DEST/tms_agent/__pycache__" "$DEST/tms_agent/tools/__pycache__" "$DEST/tests/__pycache__"

cat <<MSG
Copied into $DEST.
Next, from $DEST:
  uv add "google-adk>=2.0" google-cloud-bigquery "psycopg[binary]" psycopg-pool duckdb python-dotenv
  uv add --dev pytest pytest-asyncio reportlab
  cp tms_agent/.env.example tms_agent/.env            # set GOOGLE_CLOUD_PROJECT
  uv run python -m tms_data.generate && uv run python -m tms_data.load --target duckdb
  uv run pytest -q tests
  uv run adk web .                                   # pick tms_agent or restaurant_concierge
Merge AGENTS.tms.md into AGENTS.md and the constitution notes in specs/ if you want them always on.
MSG
