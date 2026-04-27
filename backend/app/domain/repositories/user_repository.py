"""
User repository — all DB queries for users.
Every query must use workspace context where applicable.
"""
from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.domain.models.user import User
from app.domain.enums.auth_enums import UserStatus


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_provider(self, auth_provider: str, provider_subject: str) -> Optional[User]:
        return (
            self.db.query(User)
            .filter(
                User.auth_provider == auth_provider,
                User.provider_subject == provider_subject,
            )
            .first()
        )

    def create(
        self,
        email: str,
        auth_provider: str,
        provider_subject: str,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> User:
        user = User(
            email=email,
            auth_provider=auth_provider,
            provider_subject=provider_subject,
            full_name=full_name,
            avatar_url=avatar_url,
            status=UserStatus.ACTIVE,
        )
        self.db.add(user)
        self.db.flush()
        return user

    def update_last_login(self, user_id: uuid.UUID, login_time: datetime) -> None:
        self.db.query(User).filter(User.id == user_id).update(
            {"last_login_at": login_time, "updated_at": login_time}
        )