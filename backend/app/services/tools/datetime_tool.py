from datetime import datetime, timezone

from app.services.tools.base import Tool


class CurrentDateTimeTool(Tool):
    name = "current_datetime"
    description = "Returns the current UTC date and time. Args: {} (no arguments needed)"

    def run(self, args: dict) -> str:
        return datetime.now(timezone.utc).isoformat()
