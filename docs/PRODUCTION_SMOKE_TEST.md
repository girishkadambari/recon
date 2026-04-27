# Production Deployment Smoke Test Checklist

Execute this strict end-to-end traversal confirming structural integrity mapped against explicit hostname rules to ensure SettleProof is functionally deploying correctly.

## 1. Gateway Resolution Validations

1. [ ] Open `https://cloud.settleproof.app/health` and verify `200 OK` status string.
2. [ ] Open `https://cloud.settleproof.app/docs` and confirm the Swagger UI natively loads CSS schemas correctly (Validates exact proxying).
3. [ ] Open `https://cloud.settleproof.app/ui/` and ensure the React SPA paints the Login view without blank white screens.

## 2. Authentication Integrity

4. [ ] Login with Google (or Dev Login if intentionally left active natively).
5. [ ] Observe the redirect bounce correctly landing you back natively onto `https://cloud.settleproof.app/ui/app/...` without dropping context constraints.

## 3. Data Processing Verification

6. [ ] Upload gateway CSV format file manually.
7. [ ] Upload bank CSV format file manually.
8. [ ] Preview files intuitively in UI mapping structures rendering natively.
9. [ ] Suggest column mapping cleanly natively processing via asynchronous backend endpoints.
10. [ ] Confirm mapping cleanly locking data constraints.
11. [ ] Normalize files (Validates large synchronous process capacity directly against database connection speeds).

## 4. Reconciliation Core

12. [ ] Create reconciliation run.
13. [ ] Run reconciliation and observe loading parameters securely returning success hooks contextually.
14. [ ] Open exceptions tab effectively observing structural variations instantly calculated.
15. [ ] Open exception audit drawer examining precise delta outputs securely.

## 5. Insight & Output Loop

16. [ ] Verify calculation proofs match explicit raw records completely.
17. [ ] Add resolution reason and textual note.
18. [ ] Mark exception logically as explicitly resolved.
19. [ ] Export XLSX payload.
20. [ ] Download XLSX and verify integrity physically inside mapping applications (e.g., Excel/Numbers).

## 6. Zero Bleed Security Rules

21. [ ] Confirm strictly zero browser console `500 Server Errors` existing quietly without exception boundaries.
22. [ ] Confirm server backend logs deliberately ignore secrets, database links, and explicitly mask row-level external financial attributes perfectly correctly mapped inside log parameters logic limits securely without fault.
