import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.db.models.animation_document import AnimationDocument
from app.db.models.brand_kit import BrandKit
from app.db.models.creative_asset import CreativeAsset
from app.db.models.creative_project import CreativeProject
from app.db.models.motion_project import MotionProject
from app.db.models.user import User
from app.db.models.vector_document import VectorDocument
from app.schemas.creative import (
    BrandKitCreate,
    BrandKitPatch,
    BrandKitRead,
    CreativeAssetAttach,
    CreativeAssetRead,
    CreativeGenerateAssetRequest,
    CreativeProjectCreate,
    CreativeProjectPatch,
    CreativeProjectRead,
)
from app.schemas.vector import VectorDocumentRead
from app.services.creative_service import brand_guidance
from app.services.llm_client import get_llm_client
from app.services.llm_provider import LLMProvider
from app.services.vector_service import VectorGenerationError, create_document_from_scene

settings = get_settings()
router = APIRouter(prefix="/creative", tags=["creative"])

_ASSET_TYPE_MODELS = {
    "VECTOR": VectorDocument,
    "ANIMATION": AnimationDocument,
    "MOTION": MotionProject,
}


def _get_owned_brand_kit(db: Session, brand_kit_id: uuid.UUID, user: User) -> BrandKit:
    brand_kit = db.get(BrandKit, brand_kit_id)
    if brand_kit is None or brand_kit.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand kit not found")
    return brand_kit


def _get_owned_creative_project(db: Session, project_id: uuid.UUID, user: User) -> CreativeProject:
    project = db.get(CreativeProject, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Creative project not found")
    return project


def _get_owned_creative_asset(db: Session, project: CreativeProject, asset_id: uuid.UUID) -> CreativeAsset:
    asset = db.get(CreativeAsset, asset_id)
    if asset is None or asset.creative_project_id != project.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


def _resolve_and_check_asset_ownership(db: Session, asset_type: str, asset_id: uuid.UUID, user: User) -> None:
    model = _ASSET_TYPE_MODELS[asset_type]
    row = db.get(model, asset_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{asset_type.title()} asset not found"
        )


# --- Brand kits ---


@router.post("/brand-kits", response_model=BrandKitRead, status_code=status.HTTP_201_CREATED)
def create_brand_kit(payload: BrandKitCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    brand_kit = BrandKit(user_id=user.id, **payload.model_dump())
    db.add(brand_kit)
    db.commit()
    db.refresh(brand_kit)
    return brand_kit


@router.get("/brand-kits", response_model=list[BrandKitRead])
def list_brand_kits(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(BrandKit).filter(BrandKit.user_id == user.id).order_by(BrandKit.created_at.desc()).all()


@router.get("/brand-kits/{brand_kit_id}", response_model=BrandKitRead)
def get_brand_kit(brand_kit_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_brand_kit(db, brand_kit_id, user)


@router.patch("/brand-kits/{brand_kit_id}", response_model=BrandKitRead)
def update_brand_kit(
    brand_kit_id: uuid.UUID,
    payload: BrandKitPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    brand_kit = _get_owned_brand_kit(db, brand_kit_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(brand_kit, field, value)
    db.commit()
    db.refresh(brand_kit)
    return brand_kit


@router.delete("/brand-kits/{brand_kit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand_kit(brand_kit_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    brand_kit = _get_owned_brand_kit(db, brand_kit_id, user)
    db.delete(brand_kit)
    db.commit()


# --- Creative projects ---


@router.post("/projects", response_model=CreativeProjectRead, status_code=status.HTTP_201_CREATED)
def create_creative_project(
    payload: CreativeProjectCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    if payload.brand_kit_id is not None:
        _get_owned_brand_kit(db, payload.brand_kit_id, user)
    project = CreativeProject(user_id=user.id, title=payload.title, brand_kit_id=payload.brand_kit_id)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[CreativeProjectRead])
def list_creative_projects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(CreativeProject)
        .filter(CreativeProject.user_id == user.id)
        .order_by(CreativeProject.created_at.desc())
        .all()
    )


@router.get("/projects/{project_id}", response_model=CreativeProjectRead)
def get_creative_project(project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _get_owned_creative_project(db, project_id, user)


@router.patch("/projects/{project_id}", response_model=CreativeProjectRead)
def update_creative_project(
    project_id: uuid.UUID,
    payload: CreativeProjectPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = _get_owned_creative_project(db, project_id, user)
    updates = payload.model_dump(exclude_unset=True)
    if "brand_kit_id" in updates and updates["brand_kit_id"] is not None:
        _get_owned_brand_kit(db, updates["brand_kit_id"], user)
    for field, value in updates.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_creative_project(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    project = _get_owned_creative_project(db, project_id, user)
    db.delete(project)
    db.commit()


# --- Assets (membership) ---


@router.post("/projects/{project_id}/assets", response_model=CreativeAssetRead, status_code=status.HTTP_201_CREATED)
def attach_asset(
    project_id: uuid.UUID,
    payload: CreativeAssetAttach,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = _get_owned_creative_project(db, project_id, user)
    if len(project.assets) >= settings.creative_max_assets_per_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A creative project can have at most {settings.creative_max_assets_per_project} assets.",
        )
    _resolve_and_check_asset_ownership(db, payload.asset_type, payload.asset_id, user)

    asset = CreativeAsset(
        creative_project_id=project.id,
        asset_type=payload.asset_type,
        asset_id=payload.asset_id,
        label=payload.label,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.delete("/projects/{project_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def detach_asset(
    project_id: uuid.UUID,
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Removes the membership row only — never deletes the underlying Vector/Animation/
    Motion resource, which may belong to other projects or stand alone."""
    project = _get_owned_creative_project(db, project_id, user)
    asset = _get_owned_creative_asset(db, project, asset_id)
    db.delete(asset)
    db.commit()


@router.post("/projects/{project_id}/assets/generate", response_model=VectorDocumentRead, status_code=status.HTTP_201_CREATED)
async def generate_asset(
    project_id: uuid.UUID,
    payload: CreativeGenerateAssetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    llm_client: LLMProvider = Depends(get_llm_client),
):
    project = _get_owned_creative_project(db, project_id, user)
    if len(project.assets) >= settings.creative_max_assets_per_project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A creative project can have at most {settings.creative_max_assets_per_project} assets.",
        )

    brand_kit = db.get(BrandKit, project.brand_kit_id) if project.brand_kit_id else None
    guidance = brand_guidance(brand_kit)
    full_prompt = f"{guidance}\n\n{payload.prompt}" if guidance else payload.prompt

    purpose_defaults = settings.vector_purpose_defaults[payload.purpose]
    canvas_width = payload.canvas_width if payload.canvas_width is not None else purpose_defaults["canvas_width"]
    canvas_height = payload.canvas_height if payload.canvas_height is not None else purpose_defaults["canvas_height"]
    max_objects = min(purpose_defaults["max_objects"], settings.vector_max_objects_per_document)

    if not (1 <= canvas_width <= settings.vector_canvas_max_width) or not (
        1 <= canvas_height <= settings.vector_canvas_max_height
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"canvas dimensions must be between 1 and {settings.vector_canvas_max_width}x"
            f"{settings.vector_canvas_max_height}.",
        )

    try:
        document = await create_document_from_scene(
            db,
            user.id,
            llm_client,
            settings.ollama_model,
            full_prompt,
            payload.purpose,
            canvas_width,
            canvas_height,
            max_objects,
            settings.vector_max_retries,
        )
    except VectorGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    db.add(
        CreativeAsset(
            creative_project_id=project.id,
            asset_type="VECTOR",
            asset_id=document.id,
            label=payload.label,
        )
    )
    db.commit()
    return document
