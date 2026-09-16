import json
import re
import uuid
from datetime import datetime, timezone

from app.services.tools.base import Tool, ToolCallResult, ToolContext
from app.services.tools.calculator import CalculatorTool
from app.services.tools.datetime_tool import CurrentDateTimeTool
from app.services.tools.image_generation_tool import GenerateImageTool
from app.services.tools.read_code_file import ReadCodeFileTool
from app.services.tools.search_memories import SearchMemoriesTool

TOOL_REGISTRY: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        CalculatorTool(),
        CurrentDateTimeTool(),
        ReadCodeFileTool(),
        SearchMemoriesTool(),
        GenerateImageTool(),
    ]
}

_TOOL_CALL_PATTERN = re.compile(r"```tool\s*\n(.*?)\n```", re.DOTALL)
# Small local models don't always reproduce the exact fenced-block format asked for in the
# system prompt — they sometimes emit the bare JSON object as their entire reply instead.
# Only matches when the WHOLE stripped reply is one JSON object (never a substring), so a
# normal answer that happens to mention or contain JSON is never misread as a tool call.
_BARE_TOOL_CALL_PATTERN = re.compile(r'^\{\s*"tool"\s*:.*\}$', re.DOTALL)

# Requires a creation verb AND a visual-media noun AND an explicit connector before the
# description — e.g. "create an image of X", "generate a picture showing X", "make a logo
# for X", "create image: X" — deliberately narrow so it can't misfire on something like
# "create an image processing script" (no connector after the noun) or "make a plan for the
# launch" (no media noun). See extract_explicit_image_request.
_IMAGE_REQUEST_PATTERN = re.compile(
    r"^(?:please\s+)?(?:create|generate|draw|make|paint)\s+(?:an?\s+)?"
    r"(?:image|picture|photo|illustration|logo|drawing|artwork)\s*"
    r"(?:of|showing|depicting|featuring|for|:|-|,)\s*(.+)$",
    re.IGNORECASE,
)


def get_current_datetime_context() -> str:
    """A one-line grounding fact injected directly into the system prompt on every turn,
    regardless of tools_enabled or which model is answering. No LLM knows "right now" from
    training no matter how recently it was trained — the previous design left the model to
    either invoke the current_datetime tool (only when tools were enabled, and only if the
    model reliably emitted the fenced-block call — a small local model often doesn't) or
    guess, which is how "what's the date?" produced a hallucinated year. Handing the real
    answer over unconditionally, every turn, isn't dependent on model behavior at all."""
    now = datetime.now(timezone.utc)
    return f"Current date and time (UTC): {now.strftime('%A, %B %d, %Y, %H:%M')} ({now.isoformat()})."


def get_tools_system_prompt(code_project_active: bool = False) -> str:
    # read_code_file can never succeed outside a code-project conversation (there's no
    # project for it to read from) — advertising it anyway is what led a small model to
    # "answer" a plain coding question by hallucinating a call to it, copying the arg
    # placeholders from its own description verbatim instead of writing the code.
    visible_tools = [
        tool for tool in TOOL_REGISTRY.values() if code_project_active or tool.name != "read_code_file"
    ]
    tool_lines = "\n".join(f"- {tool.name}: {tool.description}" for tool in visible_tools)
    return (
        "You have access to these tools:\n"
        f"{tool_lines}\n\n"
        "To use one, respond with ONLY a fenced block in exactly this format (no other text "
        "in that response):\n"
        '```tool\n{"tool": "<name>", "args": {...}}\n```\n'
        "You will then receive the tool's result and can give your final answer. Only use a "
        "tool when it's actually needed to answer the question — most turns need none of them. "
        "Never mention, list, or comment on this tool list in a normal reply (e.g. 'this code "
        "doesn't use the generate_image tool'); it exists for you to call, not to discuss. If a "
        "tool isn't relevant, just answer the question directly as if this note weren't here."
    )


def extract_explicit_image_request(text: str) -> str | None:
    """An unmistakably-phrased image request ('create an image of X', 'generate a picture
    showing X', 'draw a logo for X', 'create image: X'...) is routed straight to the
    generate_image tool instead of relying on the model to notice and emit a correctly
    formatted tool call itself — a small local model will often just answer in plain text, or
    invent unrelated code, rather than follow the fenced-block instruction in
    get_tools_system_prompt. Returns the extracted description, or None if `text` doesn't
    match (see _IMAGE_REQUEST_PATTERN for exactly how narrow that match is)."""
    match = _IMAGE_REQUEST_PATTERN.match(text.strip())
    if not match:
        return None
    prompt = match.group(1).strip().rstrip(".!")
    return prompt or None


def looks_like_tool_call_start(text: str) -> bool:
    """True if `text` — the reply so far, possibly still mid-stream and incomplete — could be
    the start of a tool call: either the fenced form, or a small model's bare-JSON attempt at
    one. Used to hold back live display of a reply's opening characters until there's enough
    to tell (see stream_assistant_reply), so raw tool-call syntax never flashes into the chat
    as if it were the answer. Deliberately the same "opening shape" as _BARE_TOOL_CALL_PATTERN
    — kept as one function so the two checks can't drift apart."""
    stripped = text.lstrip()
    return stripped.startswith("```tool") or bool(re.match(r'^\{\s*"tool"', stripped))


async def maybe_run_tool_call(assistant_reply: str, context: ToolContext | None = None) -> ToolCallResult | None:
    match = _TOOL_CALL_PATTERN.search(assistant_reply)
    if match:
        candidate = match.group(1)
    else:
        stripped = assistant_reply.strip()
        candidate = stripped if _BARE_TOOL_CALL_PATTERN.match(stripped) else None
    if candidate is None:
        return None

    try:
        payload = json.loads(candidate)
        tool_name = payload["tool"]
        args = payload.get("args", {})
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    tool = TOOL_REGISTRY.get(tool_name)
    if tool is None:
        return ToolCallResult(tool_name=tool_name, result=f"Error: unknown tool '{tool_name}'")

    result = await tool.run(args, context)

    # generate_image (and any future tool that produces a viewable attachment) encodes its
    # result as JSON — {"message": <text for the model>, "image_id": <optional uuid>} — so it
    # can hand back both a clean model-facing message and a structured, typed attachment
    # reference in one call, without every other plain-text tool's return value needing to
    # carry this shape too.
    image_id: uuid.UUID | None = None
    if tool_name == "generate_image":
        try:
            parsed = json.loads(result)
            if parsed.get("image_id"):
                image_id = uuid.UUID(parsed["image_id"])
            result = parsed.get("message", result)
        except (json.JSONDecodeError, KeyError, ValueError, AttributeError, TypeError):
            pass

    return ToolCallResult(tool_name=tool_name, result=result, image_id=image_id)
