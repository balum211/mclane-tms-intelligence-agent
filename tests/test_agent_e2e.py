"""End-to-end run of the ADK agent tree with a scripted (offline) model.

Proves the wiring without Gemini credentials: coordinator -> AgentTool(freight_cost_analyst)
-> get_accessorial_leakage -> DuckDB, and the specialist's answer flows back to the user.
"""

import json
from typing import AsyncGenerator

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class ScriptedLlm(BaseLlm):
    """Calls one tool per agent, then summarises the tool result as text."""

    model: str = "scripted"

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1]
        responses = [p.function_response for p in last.parts or [] if p.function_response]
        if responses:
            payload = json.dumps(responses[0].response, default=str)
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text=f"RESULT {payload[:2000]}")]))
            return
        tools = llm_request.tools_dict
        if "freight_cost_analyst" in tools:
            call = types.FunctionCall(name="freight_cost_analyst", args={"request": "Unbilled detention, last 60 days"})
        elif "get_accessorial_leakage" in tools:
            call = types.FunctionCall(name="get_accessorial_leakage", args={"days": 60})
        else:
            raise AssertionError(f"unexpected agent tools {list(tools)}")
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))


@pytest.mark.asyncio
async def test_coordinator_delegates_to_cost_analyst():
    from tms_agent.agent import build_root_agent

    agent = build_root_agent(model=ScriptedLlm(), sql_model=ScriptedLlm())
    runner = Runner(app_name="tms_test", agent=agent, session_service=InMemorySessionService(),
                    auto_create_session=True)
    final, tool_calls = None, []
    async for event in runner.run_async(
        user_id="u1", session_id="s1",
        new_message=types.Content(role="user", parts=[types.Part(text="Where are we leaking accessorial revenue?")]),
    ):
        for fc in event.get_function_calls():
            tool_calls.append(fc.name)
        if event.is_final_response() and event.content and event.content.parts:
            final = event.content.parts[0].text
    assert "freight_cost_analyst" in tool_calls
    assert final and "BurgerBarn" in final


class TenderLlm(BaseLlm):
    """Coordinator that immediately tenders a load (to exercise ADK human-in-the-loop confirmation)."""

    model: str = "scripted-tender"
    load_id: str = ""
    carrier_id: str = ""

    async def generate_content_async(self, llm_request: LlmRequest, stream: bool = False) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1]
        if any(p.function_response for p in last.parts or []):
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Tender submitted for approval.")]))
            return
        call = types.FunctionCall(name="tender_load", args={"load_id": self.load_id, "carrier_id": self.carrier_id})
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))


@pytest.mark.asyncio
async def test_tender_over_cap_pauses_for_human_confirmation(monkeypatch):
    from tms_agent.agent import build_root_agent
    from tms_agent.tools.carrier import recommend_carrier_for_load
    from tms_agent.tools.common import run

    monkeypatch.setenv("TMS_AUTO_TENDER_MAX_USD", "1")
    load_id = run("SELECT load_id FROM {p}loads WHERE load_status IN ('PLANNED','DISPATCHED') ORDER BY load_id LIMIT 1")[0]["load_id"]
    carrier_id = recommend_carrier_for_load(load_id)["data"]["recommended"]["carrier_id"]
    agent = build_root_agent(model=TenderLlm(load_id=load_id, carrier_id=carrier_id), sql_model=ScriptedLlm())
    runner = Runner(app_name="tms_test", agent=agent, session_service=InMemorySessionService(),
                    auto_create_session=True)
    calls = []
    async for event in runner.run_async(
        user_id="u1", session_id="s2",
        new_message=types.Content(role="user", parts=[types.Part(text=f"Tender {load_id}")]),
    ):
        calls += [fc.name for fc in event.get_function_calls()]
    assert "tender_load" in calls
    assert "adk_request_confirmation" in calls
