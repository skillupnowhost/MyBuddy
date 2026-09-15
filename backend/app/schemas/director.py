import uuid

from pydantic import BaseModel


class DirectorFilmCreate(BaseModel):
    idea: str
    title: str | None = None
    character_ids: list[uuid.UUID] = []
    world_bible_id: uuid.UUID | None = None
    generate_video: bool = True
