"""
Seed data loader — production-quality script to bootstrap a 
fully-functional demo/staging environment using real sample files.

Usage:
  cd backend
  python -m app.scripts.seed_data
"""
import sys
from pathlib import Path

# ── ensure backend root is in path ───────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.database import SessionLocal
from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_member import WorkspaceMember
from app.domain.enums.workspace_enums import WorkspaceRole
from app.domain.services.sample_data_loader import SampleDataLoader


def _get_or_create_demo_context(db):
    """Returns (user, workspace)."""
    email = "demo@reconworker.ai"
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            display_name="Demo User",
            is_active=True,
            hashed_password="...", 
        )
        db.add(user)
        db.flush()

        ws = Workspace(name="Demo Workspace", slug="demo", owner_user_id=user.id)
        db.add(ws)
        db.flush()

        member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER)
        db.add(member)
        db.commit()
    else:
        ws = db.query(Workspace).filter(Workspace.owner_user_id == user.id).first()
    
    return user, ws


def run():
    print("\n🌱 Production Seed Data Loader")
    print("=" * 50)
    
    db = SessionLocal()
    try:
        user, ws = _get_or_create_demo_context(db)
        print(f"  ✅ Demo context ready: {user.email} in {ws.name}")

        print("\n[1/2] Loading production samples via real services...")
        loader = SampleDataLoader(db)
        run = loader.load_production_demo(ws.id, user.id)
        
        print(f"  ✅ Reconciliation Run COMPLETED: {run.id}")
        print(f"  📊 Match Rate:    {run.match_rate_pct}%")
        print(f"  📊 Matched:       {run.matched_count}")
        print(f"  📊 Exceptions:    {run.exception_count}")

        print("\n[2/2] Audit & Next Steps")
        print("  - Files are uploaded to S3/LocalStack")
        print("  - Records are normalized in PostgreSQL")
        print("  - Matches and Exceptions are persisted")
        print("\n🚀 Ready for demo!")
        
    finally:
        db.close()
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run()
