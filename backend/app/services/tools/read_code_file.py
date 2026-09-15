import uuid

from app.db.models.code_file import CodeFile
from app.db.models.code_project import CodeProject
from app.services.tools.base import Tool, ToolContext

_MAX_READ_CHARS = 8000


class ReadCodeFileTool(Tool):
    """Read-only, ownership-scoped: only files inside a CodeProject the calling user owns.
    No writes, no path outside what the project extraction already recorded (relative_path
    is looked up in the DB, never joined onto storage_path directly from the model's input),
    no directory listing (the model must already know the path — from code RAG context, not
    from this tool)."""

    name = "read_code_file"
    description = (
        'Reads a text file from one of your own uploaded code projects. Args: '
        '{"project_id": "<uuid>", "path": "<relative path within the project>"}'
    )

    async def run(self, args: dict, context: ToolContext | None = None) -> str:
        if context is None:
            return "Error: this tool requires an authenticated context."

        project_id = args.get("project_id")
        path = args.get("path")
        if not project_id or not path:
            return "Error: 'project_id' and 'path' are required."

        try:
            project_uuid = uuid.UUID(str(project_id))
        except ValueError:
            return "Error: 'project_id' must be a valid UUID."

        project = context.db.get(CodeProject, project_uuid)
        if project is None or project.user_id != context.user_id:
            return "Error: code project not found."

        file = (
            context.db.query(CodeFile)
            .filter(CodeFile.project_id == project_uuid, CodeFile.relative_path == path)
            .first()
        )
        if file is None:
            return f"Error: file '{path}' not found in that project."

        try:
            with open(file.storage_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(_MAX_READ_CHARS + 1)
        except OSError:
            return "Error: could not read that file from storage."

        if len(content) > _MAX_READ_CHARS:
            return content[:_MAX_READ_CHARS] + f"\n... (truncated at {_MAX_READ_CHARS} characters)"
        return content
