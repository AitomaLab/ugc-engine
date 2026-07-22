---
paths:
  - "services/creative-os/**/*"
---
# Creative OS service rules

- New endpoints go in `routers/`, with the router's own prefix set via `APIRouter(prefix="/xxx")` and mounted under `/creative-os` in `main.py` (see `routers/brands.py` for the pattern).
- Any endpoint touching user-owned data must depend on `get_current_user` (or `get_optional_user` where anonymous access is intended) from `auth.py` — don't hand-roll auth.
- Env vars load via `env_loader.load_env()`, which walks up from the current file to find `.env.saas`/`.env` — no separate env file is needed for this service locally.
- This directory keeps its own local copies of `prompts/*.py`, `elevenlabs_client.py`, and `config.py` that shadow the repo-root versions at import time — if you edit the root copies, update these local copies too or Creative OS won't see the change.
- Same for `services/brief_composer.py` and `services/industry_taxonomy.py`: byte-identical shadows of `ugc_backend/research/*` (the standalone Railway container has no `ugc_backend`). A test in `tests/test_brand_strategy.py` fails when they drift — recopy from the canonical root files.
