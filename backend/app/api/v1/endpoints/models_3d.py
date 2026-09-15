import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.model_3d import Model3D
from app.db.models.user import User
from app.services.storage import delete_upload

_CONTENT_TYPES = {"obj": "text/plain", "ply": "application/octet-stream"}

router = APIRouter(prefix="/models3d", tags=["models3d"])


def _get_owned_model_3d(db: Session, model_3d_id: uuid.UUID, user: User) -> Model3D:
    model = db.get(Model3D, model_3d_id)
    if model is None or model.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="3D model not found")
    return model


@router.get("/{model_3d_id}")
def get_model_3d(model_3d_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Served only through this authenticated endpoint, same reasoning as images.get_image
    and videos.get_video."""
    model = _get_owned_model_3d(db, model_3d_id, user)
    content_type = _CONTENT_TYPES.get(model.format, "application/octet-stream")
    return FileResponse(model.storage_path, media_type=content_type)


@router.delete("/{model_3d_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_3d(model_3d_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    model = _get_owned_model_3d(db, model_3d_id, user)
    delete_upload(model.storage_path)
    db.delete(model)
    db.commit()
