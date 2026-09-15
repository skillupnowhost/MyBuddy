import pytest

from app.services.tools import maybe_run_tool_call
from app.services.tools.calculator import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_evaluates_basic_expression():
    tool = CalculatorTool()
    assert await tool.run({"expression": "2 + 2 * 3"}) == "8"


@pytest.mark.asyncio
async def test_calculator_rejects_code_injection():
    tool = CalculatorTool()
    # Anything beyond numeric literals + arithmetic operators must be rejected outright —
    # this must never become a general eval().
    result = await tool.run({"expression": "__import__('os').system('echo pwned')"})
    assert result.startswith("Error")


@pytest.mark.asyncio
async def test_calculator_rejects_name_lookup():
    tool = CalculatorTool()
    result = await tool.run({"expression": "open('secret.txt').read()"})
    assert result.startswith("Error")


@pytest.mark.asyncio
async def test_maybe_run_tool_call_executes_calculator():
    reply = 'Sure, let me compute that.\n```tool\n{"tool": "calculator", "args": {"expression": "10 / 2"}}\n```'
    result = await maybe_run_tool_call(reply)
    assert result is not None
    assert result.tool_name == "calculator"
    assert result.result == "5.0"


@pytest.mark.asyncio
async def test_maybe_run_tool_call_returns_none_for_plain_reply():
    result = await maybe_run_tool_call("Just a normal reply with no tool usage.")
    assert result is None


@pytest.mark.asyncio
async def test_maybe_run_tool_call_reports_unknown_tool():
    reply = '```tool\n{"tool": "shell", "args": {"cmd": "rm -rf /"}}\n```'
    result = await maybe_run_tool_call(reply)
    assert result is not None
    assert "unknown tool" in result.result.lower()
