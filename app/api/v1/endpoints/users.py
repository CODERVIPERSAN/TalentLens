from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.db.session import get_db
from app.schemas.user import User, UserUpdate
from app.db.models.user import User as UserModel

router = APIRouter()


@router.get("/me", response_model=User)
async def read_users_me(db: AsyncSession = Depends(get_db)):
    # TODO: Implement authentication dependency
    result = await db.execute(select(UserModel).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/me", response_model=User)
async def update_user_me(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db)
):
    # TODO: Implement authentication dependency
    result = await db.execute(select(UserModel).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        from app.core.security import get_password_hash
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)
    return user
