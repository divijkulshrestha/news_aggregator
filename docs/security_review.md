# Security & Code Quality Review

Part of Phase 2.5 (Code Quality) in [PROJECT_PLAN.md](PROJECT_PLAN.md). Covers a manual review
of `backend/`, `etl/`, and `frontend/app.js`. Findings from the diff-only automated review
(docs cleanup, unused file deletion) are not included — that pass found nothing.

**Review date:** 2026-08-22
**Scope reviewed:** `backend/app.py`, `backend/database.py`, `backend/digest.py`,
`etl/ingest_and_process.py`, `etl/etl_news.py`, `frontend/app.js`, `frontend/feeds.js`,
`frontend/index.html`, `frontend/feeds.html`, `scripts/seed_feeds.py`, `scripts/send_digest.py`,
`scripts/run_etl.py`
**Reviewed, no findings:** `frontend/styles.css`, `frontend/feeds.css` (presentation-only, no
security/correctness surface)

## Summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | [Stored XSS via unescaped article fields](#1-stored-xss-via-unescaped-article-fields) | High | Fixed |
| 2 | [No SSRF/URL validation on feed URLs](#2-no-ssrfurl-validation-on-feed-urls) | High | Fixed |
| 3 | [Feed management page has no access control](#3-feed-management-page-has-no-access-control) | Medium | Open |
| 4 | [CORS wildcard origin with credentials](#4-cors-wildcard-origin-with-credentials) | Medium | Open |
| 5 | [Unauthenticated + duplicated cleanup logic](#5-unauthenticated--duplicated-cleanup-logic) | Medium | Fixed |
| 6 | [Hardcoded default DB credentials](#6-hardcoded-default-db-credentials) | Medium | Fixed |
| 7 | [No structured logging in backend](#7-no-structured-logging-in-backend) | Low | Fixed |
| 8 | [Row-by-row dedup instead of bulk upsert](#8-row-by-row-dedup-instead-of-bulk-upsert) | Low | Fixed |
| 9 | [Inline per-function imports; incomplete type hints](#9-inline-per-function-imports-incomplete-type-hints) | Low | Fixed |

---

## 1. Stored XSS via unescaped article fields

- **Severity:** High
- **Status:** Fixed — `article.title`, `article.category` (raw and label), and
  `article.summary` are now routed through `escapeHtml()`; `article.link` is validated as
  `http(s)`-only and escaped before being placed in `href` (falls back to `#` otherwise).
- **Location:** [frontend/app.js:348](../frontend/app.js#L348) (`createArticleCard`)

`createArticleCard()` interpolates `article.title`, `article.summary`, `article.link`, and
`article.category` directly into `innerHTML` without escaping. `frontend/feeds.js` shows the
correct pattern already exists in the codebase (`escapeHtml()`), it's just not used here.

**Failure scenario:** An RSS source (or a malicious feed added via the feed-management UI)
publishes an article with a title like `<img src=x onerror=alert(document.cookie)>`. The ETL's
`_clean_html()` in `etl/ingest_and_process.py` only strips tags via BeautifulSoup and then
`html.unescape()`s entities — it does not re-encode for HTML output. When rendered client-side,
the payload executes in the viewer's browser.

**Why it matters now vs. later:** Low impact today (no cookie-based auth or sessions exist), but
becomes a real risk the moment auth or multi-user/shared deployment is added — which is exactly
the direction Phase 3+ heads.

**Suggested fix:** Route `article.title`, `article.summary`, and `article.category` through the
existing `escapeHtml()` helper before interpolation. `article.link` should also be escaped when
placed in the `href` attribute (and ideally validated as `http(s)` scheme only).

---

## 2. No SSRF/URL validation on feed URLs

- **Severity:** High
- **Status:** Fixed — new [url_safety.py](../url_safety.py) `validate_feed_url()` enforces
  http(s)-only schemes and rejects private/loopback/link-local/multicast/reserved IP ranges
  (post-DNS-resolution). Enforced at persistence time (`POST`/`PATCH /api/feeds`) and again at
  fetch time in `fetch_feed_entries()`, which also now fetches with `allow_redirects=False` and
  re-validates the redirect target before following it, closing both the DNS-rebinding and
  redirect-based SSRF gaps.
- **Location:** [backend/app.py:59-62](../backend/app.py#L59-L62) (`FeedCreate`),
  [etl/ingest_and_process.py:101](../etl/ingest_and_process.py#L101) (`fetch_feed_entries`)

`FeedCreate.url` is typed as a bare `str` with no scheme/host validation server-side (the
frontend's `<input type="url">` on `feeds.html` is client-side only and trivially bypassed via
direct API calls). Whatever is stored gets fetched by `fetch_feed_entries()` via
`requests.get(url, ...)` on every ETL run, with no restriction on target host.

**Failure scenario:** A feed URL pointing at an internal/private address (e.g.
`http://169.254.169.254/latest/meta-data/` for AWS instance metadata once deployed to ECS, or
`http://localhost:5432`) gets fetched by the ETL process on its regular schedule, and the
(non-RSS) response body gets fed through `feedparser`/`BeautifulSoup`. Even without full
response disclosure back to the attacker, this is a classic SSRF primitive against internal
infrastructure once deployed to AWS per the Phase 3/4 plan.

**Suggested fix:** Validate feed URLs server-side — restrict to `http`/`https` schemes, reject
private/link-local/loopback IP ranges (including after DNS resolution, to prevent DNS
rebinding), before persisting or fetching.

---

## 3. Feed management page has no access control

- **Severity:** Medium
- **Status:** Open
- **Location:** [frontend/feeds.html](../frontend/feeds.html),
  [backend/app.py:296-342](../backend/app.py#L296-L342) (`/api/feeds` CRUD routes)

`/feeds.html` and the underlying `/api/feeds` CRUD endpoints have no authentication. Anyone who
discovers the URL (or hits the API directly) can add, disable, or delete RSS sources.

**Failure scenario:** Combined with finding #2 (no URL validation), an anonymous visitor could
add a feed pointing at an internal address, or simply pollute the aggregator with a spam/malicious
feed that then gets fetched and rendered to the site owner. Acceptable for a single-user local
deployment, but this is exactly the kind of admin surface that needs to be gated before any
public AWS deployment.

**Suggested fix:** Add basic auth (or an API key / IP allowlist) in front of `/feeds.html` and
`/api/feeds/*` before deploying publicly.

---

## 4. CORS wildcard origin with credentials

- **Severity:** Medium
- **Status:** Open
- **Location:** [backend/app.py:27](../backend/app.py#L27)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    ...
)
```

Browsers reject the literal wildcard-origin + credentials combination for credentialed requests,
but Starlette's `CORSMiddleware` still echoes back the requesting `Origin` header verbatim when
`allow_origins` is `"*"`, effectively allowing any origin to make credentialed requests.

**Failure scenario:** Once deployed publicly with a real domain (Phase 3/4), any website could
make credentialed cross-origin requests against the API from a victim's browser.

**Why it matters now vs. later:** Low risk today (no cookie-based auth), but should be tightened
before AWS deployment — restrict `allow_origins` to the actual frontend origin(s).

---

## 5. Unauthenticated + duplicated cleanup logic

- **Severity:** Medium
- **Status:** Fixed — removed the `DELETE /api/cleanup` HTTP endpoint from `backend/app.py`
  entirely (no frontend caller referenced it). `scripts/run_etl.py`'s `cleanup_old_articles()`,
  already wired into every scheduled ETL run, is now the single implementation. README updated
  to drop the removed endpoint from the API docs.
- **Location:** [backend/app.py:186-196](../backend/app.py#L186-L196) (`DELETE /api/cleanup`),
  [scripts/run_etl.py:43-62](../scripts/run_etl.py#L43-L62) (`cleanup_old_articles`)

Two separate implementations of the same "delete articles older than 7 days, keep bookmarks"
logic exist: the HTTP endpoint in `app.py`, and a copy already wired into `run_etl.py`'s
scheduled job (called automatically after every ETL run, line 101). The HTTP endpoint appears to
be dead/redundant now that the scheduled version exists, and is also unauthenticated,
confirmation-free, and unrate-limited.

**Failure scenario:** Any client can call `DELETE /api/cleanup` and trigger an immediate,
unscheduled purge — redundant with the automatic cleanup `run_etl.py` already performs, and a
standing unauthenticated data-destructive route once the API is public.

**Suggested fix:** Remove the `/api/cleanup` HTTP endpoint (or gate it behind auth) now that
`run_etl.py` handles cleanup automatically on schedule; if kept, extract the shared filter logic
into one function both call, rather than maintaining two copies.

---

## 6. Hardcoded default DB credentials

- **Severity:** Medium
- **Status:** Fixed — added an `ENVIRONMENT` var (default `local`). The hardcoded default
  `DATABASE_URL` is only used when `ENVIRONMENT=local`; any other value with `DATABASE_URL`
  unset now raises `RuntimeError` at import time instead of silently connecting with default
  credentials. `docker-compose.yml` already sets `DATABASE_URL` explicitly for both services, so
  this is unaffected by the change. Documented in `.env.example`.
- **Location:** [backend/database.py:9](../backend/database.py#L9)

```python
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://news_user:news_password@localhost:5432/news_db"
)
```

**Failure scenario:** If `DATABASE_URL` is accidentally unset in a deployed environment (e.g. an
ECS task definition misconfiguration), the app silently connects with a well-known default
credential pair instead of failing loudly — masking a config error and creating a predictable-
credential attack surface if the DB is ever network-reachable.

**Suggested fix:** Fail fast (raise) if `DATABASE_URL` is not set in non-local environments,
rather than falling back silently.

---

## 7. No structured logging in backend

- **Severity:** Low
- **Status:** Open
- **Location:** `backend/app.py`, `backend/database.py` (`init_db`)

Only `print()` statements exist; no logging framework, levels, or request correlation. Directly
matches the open Phase 2.5 checklist item "Add logging framework."

**Why it matters:** In production (ECS/CloudWatch per the project plan), `print()` output is
unstructured and provides no way to distinguish info/warning/error severity or correlate
request failures.

---

## 8. Row-by-row dedup instead of bulk upsert

- **Severity:** Low
- **Status:** Fixed — `save_to_postgres()` now issues a single bulk
  `INSERT ... ON CONFLICT (link) DO NOTHING ... RETURNING id` via the already-imported
  `sqlalchemy.dialects.postgresql.insert`, instead of one `SELECT` per article in a Python loop.
  Verified against the live dev DB: 186 new / 450 duplicate-skipped on one run, 2 new / 1785
  duplicate-skipped on a follow-up run, matching expected incremental behavior.
- **Location:** [etl/ingest_and_process.py:219](../etl/ingest_and_process.py#L219) (`save_to_postgres`)

Issues one `SELECT` per fetched article inside a Python loop to check for existing links before
inserting, instead of a single bulk `INSERT ... ON CONFLICT`. The module already imports
`sqlalchemy.dialects.postgresql.insert` (line 231) but never uses it — likely an abandoned
refactor.

**Why it matters:** Fine at current scale (~1-2k articles), but N synchronous round-trips per
ETL run won't scale, and the dead import is a signal of unfinished work worth cleaning up.

---

## 9. Inline per-function imports; incomplete type hints

- **Severity:** Low
- **Status:** Fixed — `or_`, `and_`, and `func` moved to module-level imports in
  `backend/app.py`; every route handler now has a return type annotation. `/` and `/feeds.html`
  needed `response_model=None` added since they return a `Response` subclass directly (FastAPI
  otherwise tries to build a Pydantic response model from the annotation and fails at startup —
  caught by rebuilding and health-checking the container). Also removed the unused `engine`
  import from `etl/ingest_and_process.py` while consolidating imports there for item 8.
- **Location:** [backend/app.py:113](../backend/app.py#L113), also lines 155, 168

Several handlers re-import from `sqlalchemy` inline (`func`, `or_`, `and_`) instead of at module
top, and no function has a return type annotation despite Pydantic response models being defined
throughout. Matches the open Phase 2.5 checklist item "Add type hints throughout."

---

## Other notes (no dedicated finding)

- **`scripts/send_digest.py`** — reads SMTP credentials from environment via `python-dotenv`,
  dry-runs cleanly when unconfigured, and doesn't log credentials. No issues found.
- **`scripts/seed_feeds.py`** — one-time migration script, straightforward, no issues found.
- **`etl/etl_news.py`** — thin CLI wrapper around `ingest_and_process.py`, no issues found beyond
  what's already noted for that module.

## Review complete

All application code (`backend/`, `etl/`, `frontend/`, `scripts/`) has now been reviewed. No
further sections planned unless new code is added.
