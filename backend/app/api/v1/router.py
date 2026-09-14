from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, chat, conversations, documents, memories, models, training

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(models.router)
api_router.include_router(documents.router)
api_router.include_router(memories.router)
api_router.include_router(training.router)
api_router.include_router(admin.router)
