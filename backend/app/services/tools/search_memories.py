from app.db.models.memory import Memory
from app.services.tools.base import Tool, ToolContext

_MAX_RESULTS = 10


class SearchMemoriesTool(Tool):
    """Read-only, ownership-scoped: a fixed-shape ILIKE search over the calling user's own
    Memory rows only — deliberately not a generic/free-form database query tool, which could
    leak cross-user data or run expensive queries if the model constructed it. If a future
    tool needs richer search than a substring match, add another fixed-shape tool rather than
    loosening this one into a query builder."""

    name = "search_memories"
    description = 'Searches your own saved memories for a keyword. Args: {"query": "<keyword>"}'

    async def run(self, args: dict, context: ToolContext | None = None) -> str:
        if context is None:
            return "Error: this tool requires an authenticated context."

        query = (args.get("query") or "").strip()
        if not query:
            return "Error: 'query' is required."

        rows = (
            context.db.query(Memory)
            .filter(Memory.user_id == context.user_id, Memory.content.ilike(f"%{query}%"))
            .order_by(Memory.created_at.desc())
            .limit(_MAX_RESULTS)
            .all()
        )
        if not rows:
            return "No matching memories found."
        return "\n".join(f"- {row.content}" for row in rows)
