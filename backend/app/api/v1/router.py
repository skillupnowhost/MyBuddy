from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    animation,
    auth,
    characters,
    chat,
    code,
    conversations,
    creative,
    documents,
    image_edit,
    image_generation,
    images,
    memories,
    models,
    motion,
    storyboard,
    training,
    vector,
    video_generation,
    videos,
    workspaces,
    world_bibles,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(models.router)
api_router.include_router(documents.router)
api_router.include_router(memories.router)
api_router.include_router(training.router)
api_router.include_router(admin.router)
api_router.include_router(code.router)
api_router.include_router(images.router)
api_router.include_router(image_generation.router)
api_router.include_router(image_edit.router)
api_router.include_router(vector.router)
api_router.include_router(animation.router)
api_router.include_router(motion.router)
api_router.include_router(creative.router)
api_router.include_router(videos.router)
api_router.include_router(video_generation.router)
api_router.include_router(storyboard.router)
api_router.include_router(characters.router)
api_router.include_router(world_bibles.router)
api_router.include_router(workspaces.router)
