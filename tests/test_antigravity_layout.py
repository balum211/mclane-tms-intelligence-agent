"""The repo keeps the layout the Antigravity + spec-kit codelabs expect (sdd-adk-antigravity starter)."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPECKIT = ["analyze", "checklist", "clarify", "constitution", "implement", "plan", "specify", "tasks"]


def _frontmatter(path: Path) -> dict:
    text = path.read_text()
    assert text.startswith("---\n"), f"{path} must start with YAML frontmatter"
    return yaml.safe_load(text.split("---\n", 2)[1])


def test_skills_have_valid_frontmatter():
    skills = sorted((ROOT / ".agents/skills").glob("*/SKILL.md"))
    assert len(skills) >= 8
    for s in skills:
        fm = _frontmatter(s)
        assert fm["name"] == s.parent.name, s
        assert fm["name"] == fm["name"].lower() and " " not in fm["name"]
        assert len(fm["description"]) > 40, f"{s}: description is what triggers the skill"


def test_skill_scripts_are_referenced_by_relative_path():
    for script in (ROOT / ".agents/skills").glob("*/scripts/*.py"):
        skill_md = (script.parent.parent / "SKILL.md").read_text()
        assert f"scripts/{script.name}" in skill_md, script


def test_speckit_workflows_rules_and_memory():
    for name in SPECKIT:
        wf = ROOT / f".agents/workflows/speckit.{name}.md"
        assert "description" in _frontmatter(wf), wf
    assert (ROOT / ".agents/rules/project-context.md").is_file()
    assert (ROOT / ".specify/memory/constitution.md").is_file()
    assert (ROOT / ".specify/templates/project-context-template.md").is_file()
    for feature in (ROOT / "specs").iterdir():
        for f in ("spec.md", "plan.md", "tasks.md", "data-model.md", "research.md"):
            assert (feature / f).is_file(), feature / f


def test_toolbox_tools_yaml_uses_codelab_format():
    docs = [d for d in yaml.safe_load_all((ROOT / "tools.yaml").read_text()) if d]
    sources = {d["name"] for d in docs if d["kind"] == "source"}
    tools = [d for d in docs if d["kind"] == "tool"]
    assert sources and tools
    for t in tools:
        assert t["source"] in sources and t["type"].endswith("-sql") and t["description"]
        assert t.get("annotations", {}).get("readOnlyHint") is True


def test_env_examples_and_configs():
    root_env = (ROOT / ".env.example").read_text()
    assert "GOOGLE_CLOUD_LOCATION=global" in root_env and "REGION=" in root_env
    agent_env = (ROOT / "tms_agent/.env.example").read_text()
    assert "GOOGLE_GENAI_USE_VERTEXAI=True" in agent_env and "GOOGLE_GENAI_USE_ENTERPRISE=True" in agent_env
    mcp = json.loads((ROOT / "antigravity/mcp_config.example.json").read_text())
    assert "adk-docs-mcp" in mcp["mcpServers"]
    assert (ROOT / "uv.lock").is_file()


def test_adk_discovers_only_the_agent_package():
    import sys

    from fastapi.testclient import TestClient

    sys.path.insert(0, str(ROOT))
    import server

    assert TestClient(server.app).get("/list-apps").json() == ["tms_agent"]
