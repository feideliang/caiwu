# Copilot instructions for this repository

## Build, test, and run commands

Backend commands are run from `backend`:

```powershell
..\.venv\Scripts\python.exe -m pip install -r requirements.txt
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m pytest tests\test_api_auth.py -q
..\.venv\Scripts\python.exe -m pytest tests\test_api_auth.py::test_login_success -q
..\.venv\Scripts\python.exe -m alembic -c migrations\alembic.ini upgrade head
```

Backend tests expect PostgreSQL at `postgresql+asyncpg://learnhouse:learnhouse@localhost:5432/caiwu_test`; `tests\conftest.py` resets the public schema per test and creates tables from SQLAlchemy metadata.

Frontend commands are run from `frontend`:

```powershell
npm install
npm run dev
npm run build
npm run preview
```

Deployment uses Docker Compose from the repository root:

```powershell
docker compose -f deploy\docker-compose.yml up -d --build
```

Root-level smoke scripts are ad hoc checks:

```powershell
node test-api.js
node pw-final-test.js
node pw-qa.js
```

Those scripts hard-code local ports such as `localhost:3000` and `localhost:8000`; the Vite dev server is configured for port `3005`, and `frontend\.env.local` points API calls at `http://localhost:8000/api/v1`.

## High-level architecture

This is an AI+BI financial reporting system with a FastAPI backend in `backend\app` and a Vue 3/Vite frontend in `frontend\src`.

The backend entry point is `app.main:create_app()`. It registers CORS, `TraceIDMiddleware`, `/health`, and `app.api.router.api_v1_router`, which mounts all feature routers under `/api/v1`. Most features follow `api` router -> `schemas` Pydantic models -> `services` business logic -> SQLAlchemy `models`.

Core backend storage is PostgreSQL via async SQLAlchemy in `app\db\session.py`. `models\core.py` contains the original financial data/source/dashboard models, `models\v3.py` contains analytics/report/prediction models, and `models\v4.py` contains RBAC, audit, and notifications. Alembic imports all three model modules so migrations see the full metadata.

Data ingestion flows from BI MySQL, Excel upload, email attachments, or other configured sources into parsing/cleaning services, then through `DataSyncService` into `financial_data`. Dashboard, metrics, drilldown, insight, prediction, and report APIs aggregate from `financial_data`, with dimensional detail stored in `FinancialData.tags`.

Async work uses Celery with Redis. `app\celery_app.py` defines queues for report generation, prediction, notification, data sync, AI inference, email polling, and cache warming; `app\tasks` contains task implementations. Docker Compose runs `backend`, `celery-worker`, and `celery-beat` as separate services.

AI features combine deterministic financial rules with external Qwen-compatible APIs when configured. Business rules live in PostgreSQL as `knowledge_rule` rows and in local Qdrant storage (`qdrant_data_seed`) for RAG retrieval.

The frontend uses Vue 3, Pinia, Vue Router, Ant Design Vue, and ECharts. `src\api\request.ts` centralizes Axios setup, JWT attachment, and response handling. Feature API wrappers live in `src\api`, state lives in `src\store`, route pages live in `src\views`, and domain components are grouped under `src\components`.

## Key conventions

All normal API responses use `APIResponse` with `{ code, message, data, trace_id }`. Return `APIResponse.success(...)` from endpoints and raise `AppException` subclasses for errors that should be mapped by middleware. Frontend `ApiResponse<T>` mirrors this envelope.

Every request gets an `X-Trace-Id` from `TraceIDMiddleware`; include `trace_id` in error responses and keep the header on responses for log correlation.

Authentication uses JWT bearer tokens. The frontend stores the token as `localStorage["access_token"]` and stores user JSON as `localStorage["user"]`. Roles are `admin`, `analyst`, and `viewer`; backend guards use `get_current_user`, `require_role`, and `require_permission`. Missing or malformed bearer credentials intentionally return 403 to preserve the existing API contract.

Financial period handling commonly uses `YYYY-MM` strings for monthly data and four-digit years for yearly aggregation. Metric bucketing relies on keyword matching for names such as `revenue`/`营业收入`, `cost`/`成本`, and `gross_profit`/`毛利润`.

Dimensional analysis depends on `FinancialData.tags`. Existing services look for keys such as `department`, `sales_department`, `customer`, `customer_name`, `product_line`, `product`, `series`, `order_id`, `contract_no`, `project_name`, `region`, and `province`; preserve these aliases when adding ingestion or analytics code.

Reports and predictions are asynchronous. Report tasks use statuses and steps such as `pending`, `collecting_data`, `ai_analyzing`, `document_generating`, `completed`, and `failed`; keep API responses and frontend polling aligned with these values.

The project requirements are documented in `CLAUDE.md` and `doc\智能分析思路.md`: prioritize AI visualization recommendation, multi-source financial data ingestion, cleaning/validation, automatic KPI calculation, report generation, and forward-looking prediction. The standard business drilldown path is company -> organization/time -> customer/product -> transaction/project root cause.
