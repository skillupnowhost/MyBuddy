import json
import re

from app.services.tools.base import Tool, ToolCallResult
from app.services.tools.calculator import CalculatorTool
from app.services.tools.datetime_tool import CurrentDateTimeTool

TOOL_REGISTRY: dict[str, Tool] = {tool.name: tool for tool in [CalculatorTool(), CurrentDateTimeTool()]}

_TOOL_CALL_PATTERN = re.compile(r"```tool\s*\n(.*?)\n```", re.DOTALL)


def get_tools_system_prompt() -> str:
    tool_lines = "\n".join(f"- {tool.name}: {tool.description}" for tool in TOOL_REGISTRY.values())
    return (
        "You have access to these tools:\n"
        f"{tool_lines}\n\n"
        "To use one, respond with ONLY a fenced block in exactly this format (no other text "
        "in that response):\n"
        '```tool\n{"tool": "<name>", "args": {...}}\n```\n'
        "You will then receive the tool's result and can give your final answer. Only use a "
        "tool when it's actually needed to answer the question."
    )


async def maybe_run_tool_call(assistant_reply: str) -> ToolCallResult | None:
    match = _TOOL_CALL_PATTERN.search(assistant_reply)
    if not match:
        return None

    try:
        payload = json.loads(match.group(1))
        tool_name = payload["tool"]
        args = payload.get("args", {})
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return ToolCallResult(tool_name=tool_name, result=f"Error: unknown tool '{tool_name}'")

    result = tool.run(args)
    return ToolCallResult(tool_name=tool_name, result=result)
