"""
Seed data loader — generates realistic reconciliation sample data
and runs the full pipeline end-to-end.

Usage:
  cd backend
  python -m app.scripts.seed_data

What it does:
  1. Creates a workspace and user (alice@acme.com)
  2. Generates two realistic CSV files:
     - Stripe payment report (50 rows with known mismatches)
     - Bank statement (50 rows — 45 matched, 3 timing diffs, 2 unmatched)
  3. Uploads, maps, normalizes, and reconciles both files
  4. Prints a summary table of the run result

No demo branding — this is production-quality seed for staging/QA.
"""
import csv
import io
import os
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# ── ensure backend root is in path ───────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.database import SessionLocal
from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_member import WorkspaceMember
from app.domain.enums.workspace_enums import WorkspaceRole
from app.core.dates import utcnow
from app.auth.token_service import create_access_token

random.seed(42)


# ── Realistic data tables ─────────────────────────────────────────────────────

PAYMENT_STATUSES = ["succeeded", "succeeded", "succeeded", "succeeded", "failed", "refunded"]
CURRENCIES = ["INR", "INR", "INR", "USD"]
PAYMENT_METHODS = ["card", "upi", "netbanking", "card", "upi"]

BASE_DATE = datetime(2024, 1, 3, tzinfo=timezone.utc)


def _utr() -> str:
    return f"UTR{random.randint(100_000_000, 999_999_999)}"


def _amount() -> Decimal:
    return Decimal(str(round(random.uniform(500, 50_000), 2)))


def generate_stripe_csv(n: int = 50) -> tuple[list[dict], bytes]:
    """
    Generate a realistic Stripe payment report.
    Returns (rows_list, csv_bytes).
    """
    rows = []
    for i in range(n):
        txn_id = f"py_{uuid.uuid4().hex[:16]}"
        amount = _amount()
        status = random.choice(PAYMENT_STATUSES)
        days_ago = random.randint(0, 30)
        txn_date = BASE_DATE + timedelta(days=days_ago, hours=random.randint(0, 23))
        rows.append({
            "payment_id": txn_id,
            "amount": str(amount),
            "fee": str(round(amount * Decimal("0.02"), 2)),
            "net": str(round(amount * Decimal("0.98"), 2)),
            "currency": random.choice(CURRENCIES),
            "status": status,
            "created_at": txn_date.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_email": f"customer{i:03d}@example.com",
            "payment_method": random.choice(PAYMENT_METHODS),
            "description": f"Order #{10000+i}",
        })

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return rows, buf.getvalue().encode("utf-8")


def generate_bank_csv(stripe_rows: list[dict], match_rate: float = 0.88) -> bytes:
    """
    Generate a bank statement that deliberately matches ~match_rate% of Stripe rows.
    Introduces:
      - Exact matches (by payment_id as UTR)
      - 2-day timing difference matches
      - Amount rounding differences (1-2 INR off)
      - Completely unmatched bank credits (no Stripe counterpart)
      - Missing rows (Stripe payment not yet settled)
    """
    bank_rows = []
    succeeded = [r for r in stripe_rows if r["status"] == "succeeded"]
    n_total = len(succeeded)
    n_exact = int(n_total * 0.70)
    n_timing = int(n_total * 0.10)
    n_rounding = int(n_total * 0.08)

    shuffled = list(succeeded)
    random.shuffle(shuffled)

    # Exact matches
    for row in shuffled[:n_exact]:
        settle_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        bank_rows.append({
            "utr": row["payment_id"],
            "credit_amount": row["net"],
            "currency": row["currency"],
            "narration": f"STRIPE SETTLEMENT {row['payment_id'][:12].upper()}",
            "transaction_date": (settle_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "bank_ref": _utr(),
            "balance": str(round(random.uniform(50_000, 500_000), 2)),
        })

    # Timing difference (+3 days)
    for row in shuffled[n_exact:n_exact + n_timing]:
        settle_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        bank_rows.append({
            "utr": row["payment_id"],
            "credit_amount": row["net"],
            "currency": row["currency"],
            "narration": f"STRIPE DELAYED {row['payment_id'][:12].upper()}",
            "transaction_date": (settle_date + timedelta(days=3)).strftime("%Y-%m-%d"),
            "bank_ref": _utr(),
            "balance": str(round(random.uniform(50_000, 500_000), 2)),
        })

    # Amount rounding (off by 1-2)
    for row in shuffled[n_exact + n_timing:n_exact + n_timing + n_rounding]:
        settle_date = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S")
        original = Decimal(row["net"])
        adjusted = original - Decimal(str(round(random.uniform(0.5, 2.0), 2)))
        bank_rows.append({
            "utr": row["payment_id"],
            "credit_amount": str(adjusted),
            "currency": row["currency"],
            "narration": f"STRIPE NET {row['payment_id'][:12].upper()}",
            "transaction_date": (settle_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "bank_ref": _utr(),
            "balance": str(round(random.uniform(50_000, 500_000), 2)),
        })

    # Extra bank credits (no Stripe counterpart — e.g. refunds, other income)
    for i in range(4):
        bank_rows.append({
            "utr": _utr(),
            "credit_amount": str(round(random.uniform(100, 5000), 2)),
            "currency": "INR",
            "narration": f"NEFT TRANSFER FROM VENDOR{i}",
            "transaction_date": (BASE_DATE + timedelta(days=random.randint(1, 28))).strftime("%Y-%m-%d"),
            "bank_ref": _utr(),
            "balance": str(round(random.uniform(50_000, 500_000), 2)),
        })

    # Shuffle bank rows to make it realistic
    random.shuffle(bank_rows)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(bank_rows[0].keys()))
    writer.writeheader()
    writer.writerows(bank_rows)
    return buf.getvalue().encode("utf-8")


def _get_or_create_user(db) -> tuple:
    """Returns (user, token)."""
    from app.domain.repositories.user_repository import UserRepository
    from app.domain.repositories.workspace_repository import WorkspaceRepository

    user_repo = UserRepository(db)
    ws_repo = WorkspaceRepository(db)

    email = "alice@acme.com"
    user = user_repo.get_by_email(email)
    if not user:
        user = User(
            email=email,
            display_name="Alice (Seed User)",
            is_active=True,
            hashed_password="$2b$12$not_a_real_hash_seed_only",
        )
        db.add(user)
        db.flush()

        ws = Workspace(
            name="Acme Corp", slug="acme-corp", owner_user_id=user.id
        )
        db.add(ws)
        db.flush()

        member = WorkspaceMember(
            workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.OWNER
        )
        db.add(member)
        db.commit()
        print(f"  ✅ Created user {email} + workspace 'Acme Corp'")
    else:
        print(f"  ℹ️  User {email} already exists")

    token = create_access_token({"sub": str(user.id)})
    return user, token


def run():
    print("\n🌱 Seed Data Loader — Recon Worker")
    print("=" * 50)

    print("\n[1/4] Generating CSV files...")
    stripe_rows, stripe_csv = generate_stripe_csv(n=50)
    bank_csv = generate_bank_csv(stripe_rows)

    # Save locally for reference / manual upload
    out_dir = Path(__file__).parent / "seed_files"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "stripe_payments_jan2024.csv").write_bytes(stripe_csv)
    (out_dir / "bank_statement_jan2024.csv").write_bytes(bank_csv)

    print(f"  ✅ stripe_payments_jan2024.csv — {len(stripe_rows)} rows")
    print(f"  ✅ bank_statement_jan2024.csv — {bank_csv.count(b',')//6} rows (approx)")
    print(f"  📂 Saved to: {out_dir}")

    # Run via HTTP against local server
    print("\n[2/4] Connecting to local API...")
    try:
        import httpx
    except ImportError:
        print("  ⚠️  httpx not installed. Run: pip install httpx")
        print("  📄 CSV files are saved to seed_files/ — upload them manually via Bruno.")
        return

    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    resp = httpx.get(f"{base_url}/health", timeout=5)
    if resp.status_code != 200:
        print(f"  ❌ Server not reachable at {base_url}. Start with: uvicorn app.main:app --reload")
        return
    print(f"  ✅ Server reachable at {base_url}")

    # Login
    resp = httpx.post(f"{base_url}/api/auth/dev-login", json={"email": "alice@acme.com"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()["data"]
    token = data["access_token"]
    workspace_id = data["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  ✅ Logged in as alice@acme.com (workspace: {workspace_id[:8]}...)")

    print("\n[3/4] Uploading and normalizing files...")

    def upload_and_normalize(csv_bytes, category, mock_mapping):
        resp = httpx.post(
            f"{base_url}/api/uploads",
            data={"file_category": category},
            files={"file": (f"{category.lower()}.csv", csv_bytes, "text/csv")},
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 201, resp.text
        file_id = resp.json()["data"]["id"]

        # Suggest (calls AI)
        resp = httpx.post(f"{base_url}/api/column-mappings/{file_id}/suggest", headers=headers, timeout=30)
        if resp.status_code != 200:
            print(f"  ⚠️  AI suggest failed: {resp.text[:100]}")
        # Confirm
        resp = httpx.post(f"{base_url}/api/column-mappings/{file_id}/confirm", json=mock_mapping, headers=headers, timeout=10)
        assert resp.status_code in (200, 409), resp.text
        # Normalize
        resp = httpx.post(f"{base_url}/api/column-mappings/{file_id}/normalize", headers=headers, timeout=30)
        assert resp.status_code in (200, 409), resp.text
        return file_id

    stripe_mapping = {
        "mapping": {
            "payment_id": "transaction_id", "amount": "gross_amount",
            "fee": "fee_amount", "net": "net_amount",
            "currency": "currency", "status": "status",
            "created_at": "transaction_date", "customer_email": "customer_email",
            "payment_method": "payment_method", "description": "description",
        }
    }
    bank_mapping = {
        "mapping": {
            "utr": "utr", "credit_amount": "credit_amount",
            "currency": "currency", "narration": "narration",
            "transaction_date": "transaction_date", "bank_ref": "reference",
            "balance": "ignore",
        }
    }

    src_id = upload_and_normalize(stripe_csv, "STRIPE_REPORT", stripe_mapping)
    tgt_id = upload_and_normalize(bank_csv, "BANK_STATEMENT", bank_mapping)
    print(f"  ✅ Source file normalized: {src_id[:8]}...")
    print(f"  ✅ Target file normalized: {tgt_id[:8]}...")

    print("\n[4/4] Running reconciliation...")
    resp = httpx.post(
        f"{base_url}/api/reconciliations",
        json={"name": "January 2024 Stripe vs Bank", "source_file_id": src_id, "target_file_id": tgt_id},
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["data"]["id"]

    resp = httpx.post(f"{base_url}/api/reconciliations/{run_id}/execute", headers=headers, timeout=60)
    assert resp.status_code == 200, resp.text
    run = resp.json()["data"]

    print("\n" + "=" * 50)
    print(f"  ✅ Run completed: {run_id[:8]}...")
    print(f"  📊 Match rate:    {run['match_rate_pct']}%")
    print(f"  🔗 Matched:       {run['matched_count']} records")
    print(f"  ⚠️  Exceptions:    {run['exception_count']} records")
    print(f"  📅 Source rows:   {run['total_source_rows']}")
    print(f"  📅 Target rows:   {run['total_target_rows']}")
    print("\n📋 Next steps in Bruno:")
    print(f"   run_id = {run_id}")
    print(f"   → GET /api/reconciliations/{run_id[:8]}...")
    print(f"   → POST /api/reconciliations/{run_id[:8]}.../explain-all")
    print(f"   → POST /api/reconciliations/{run_id[:8]}.../export")
    print("=" * 50)


if __name__ == "__main__":
    run()
