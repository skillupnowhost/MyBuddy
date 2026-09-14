import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.db.models.memory import Memory
from app.db.models.user import User
from app.schemas.memory import MemoryCreate, MemoryRead

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[MemoryRead])
def list_memories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Memory).filter(Memory.user_id == user.id).order_by(Memory.created_at.desc()).all()


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    memory = Memory(user_id=user.id, content=payload.content, source="manual")
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    memory = db.get(Memory, memory_id)
    if memory is None or memory.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    db.delete(memory)
    db.commit()
