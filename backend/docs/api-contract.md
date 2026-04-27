# API Contract v0.3 (Freeze)

## General Principles
All responses follow a consistent envelope structure to facilitate frontend state management.

### Base Response Envelope
```json
{
  "data": Any,
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "has_next": true,
    "has_prev": false
  },
  "request_id": "uuid-v4-string"
}
```

### Error Envelope
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  },
  "request_id": "uuid-v4-string"
}
```

## Authentication
- **Bearer Token**: All `/api/` routes require `Authorization: Bearer <JWT>`.
- **JWT Claims**: `sub` (User ID), `email`, `active_workspace_id`, `role`.

## Endpoints

### 1. Auth & User
| Method | Path | Summary |
| :--- | :--- | :--- |
| GET | `/api/auth/google/login` | Initiate Google OAuth flow |
| GET | `/api/auth/google/callback` | OAuth callback (returns JWT) |
| POST | `/api/auth/dev-login` | Local-only bypass (returns JWT) |
| GET | `/api/auth/me` | Current user + active workspace info |

### 2. Workspaces
| Method | Path | Summary |
| :--- | :--- | :--- |
| GET | `/api/workspaces` | List user's workspaces |
| POST | `/api/workspaces` | Create new workspace |
| GET | `/api/workspaces/{id}` | Get workspace details |
| GET | `/api/workspaces/{id}/members` | List members |

### 3. File Uploads
| Method | Path | Summary |
| :--- | :--- | :--- |
| POST | `/api/uploads` | Multipart upload (CSV/XLSX) |
| GET | `/api/uploads` | List uploads |
| GET | `/api/uploads/{id}/preview` | Preview raw parsed rows |

### 4. AI Column Mapping
| Method | Path | Summary |
| :--- | :--- | :--- |
| POST | `/api/column-mappings/{id}/suggest` | Ask AI for mapping suggestions |
| POST | `/api/column-mappings/{id}/confirm` | Confirm/Edit mapping |
| POST | `/api/column-mappings/{id}/normalize`| Run normalization (Sync) |

### 5. Reconciliation Engine
| Method | Path | Summary |
| :--- | :--- | :--- |
| POST | `/api/reconciliation-runs` | Create multi-file run |
| POST | `/api/reconciliation-runs/{id}/run` | Execute matching engine |
| GET | `/api/reconciliation-runs/{id}/matches` | List confirmed/pending matches |
| GET | `/api/reconciliation-runs/{id}/exceptions`| List items requiring review |

### 6. AI & Exports
| Method | Path | Summary |
| :--- | :--- | :--- |
| POST | `/api/.../exceptions/{id}/explain` | AI explanation for mismatch |
| GET | `/api/reconciliation-runs/{id}/summary` | AI executive summary of run |
| POST | `/api/reconciliation-runs/{id}/export` | Generate XLSX report |
