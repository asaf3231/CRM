# GO_LIVE_CONFIG.md — Everything needed to take the system mock → live

> **Purpose:** one place that lists every credential, account, endpoint, and decision required to make
> the real outbound chain work (**find → analyze → ReactFirst report → send**). Fill in the blanks and
> hand the whole file (or just the filled "PASTE-BACK BLOCK" at the bottom) back in one prompt.
>
> ⚠️ **Do NOT commit real secrets.** This file is a **template with placeholders**. Real values live in a
> **gitignored `.env`** (the DB PM already set up `.env`/`.env.example` patterns). When you give me the
> filled values, I put them in `.env`, never in tracked files.
>
> **Status legend:** ❌ not set / not chosen · ⚠️ placeholder in code · ✅ provided

---

## A. Things that already have a slot in the code (just need a real value)

These env vars are **already read by the backend** — the code is written, it only needs the key.

| # | What | Env var | Used in (file) | Status | What to get |
|---|---|---|---|---|---|
| A1 | **Claude (LLM)** — reasoning loop, query-gen, analyze, Vector-A web search | `ANTHROPIC_API_KEY` | `main.py` `_get_client()` | ❌ | console.anthropic.com → API key |
| A2 | **SerpAPI** — Vector B (Google + Maps search) | `SERPAPI_API_KEY` | `main.py:430` | ❌ | serpapi.com account → key |
| A3 | **Tavily** — Vector C (recovery search) | `TAVILY_API_KEY` | `main.py:455` | ❌ | tavily.com account → key |
| A4 | **Firecrawl** — analyze/deep-crawl + pixel detection | `FIRECRAWL_API_KEY` | `main.py:833` | ❌ | firecrawl.dev account → key |
| A5 | **ReactFirst** — the weekly-report PDF API | `REACTFIRST_API_KEY` | `main.py:1126` | ❌ | **see B1 — also needs the real host** |
| A6 | **Slack** — human-approval escalation webhook | `SLACK_WEBHOOK_URL` | `main.py:2427` | ❌ | Slack → Incoming Webhook URL |
| A7 | **Database** — persistence (DB PM's layer) | `MONGO_URI` | `db.py` (DB PM) | ❌ | local Docker Mongo, or Atlas connection string |
| A8 | **Frontend → API base** (prod only; dev uses the vite proxy) | `VITE_API_URL` | `frontend/src/lib/api.ts` | ⚠️ defaults to `/api` | only needed for a deployed build |

Fill in (⚠️ real values live ONLY in gitignored `Backend/.env`, never here):
```
ANTHROPIC_API_KEY=   # ✅ provided — stored in Backend/.env
SERPAPI_API_KEY=
TAVILY_API_KEY=
FIRECRAWL_API_KEY=   # ✅ provided — stored in Backend/.env
SLACK_WEBHOOK_URL=
MONGO_URI=           # mongodb://localhost:27017 — stored in Backend/.env
```

---

## B. Decisions + accounts that DON'T exist in code yet (must be chosen, then built)

These are **not just missing keys — the integration code does not exist** and is a design decision.

### B1. ReactFirst report API — confirm the REAL endpoint
- Code currently calls a **placeholder host**: `OUTREACH_SUBDOMAIN = "outreach.reactfirst.ai"` (`main.py:99`),
  endpoint `GET https://outreach.reactfirst.ai/api/generate-pdf?domain=…&angle=…&risk=…`, `Authorization: Bearer <REACTFIRST_API_KEY>`.
- **You provide:** the real ReactFirst base URL + endpoint path + auth scheme + the request/response contract
  (does it return a PDF? JSON? what fields?). If it differs from the assumed shape, the call needs adjusting.
- Fill in:
```
REACTFIRST_BASE_URL=        # e.g. https://api.reactfirst.ai
REACTFIRST_REPORT_PATH=     # e.g. /v1/weekly-report
REACTFIRST_API_KEY=
REACTFIRST_AUTH_SCHEME=     # e.g. "Bearer" | "x-api-key header" | other
```

### B2. EMAIL sending provider — **none integrated today** (this is the real "send an email")
- Today `dispatch_outreach` only POSTs JSON to the placeholder subdomain; there is **no SMTP / no email API**.
- **Decision:** pick a provider → `[ ] Amazon SES  ·  [ ] SendGrid  ·  [ ] Postmark  ·  [ ] Mailgun  ·  [ ] plain SMTP`
- **You provide (after choosing):** provider API key (or SMTP host/user/pass), a **verified sending domain**
  with **SPF + DKIM + DMARC** set up, and the **from-address / inbox**. The design wants a **dedicated
  subdomain** separate from your corporate mail domain.
- Fill in:
```
EMAIL_PROVIDER=             # ses | sendgrid | postmark | mailgun | smtp
EMAIL_API_KEY=             # (or SMTP creds below)
SMTP_HOST=  SMTP_PORT=  SMTP_USER=  SMTP_PASS=
EMAIL_FROM=                # e.g. outbound@go.reactfirst.ai (dedicated subdomain)
EMAIL_SENDING_DOMAIN=      # the domain with SPF/DKIM/DMARC verified
DAILY_SEND_CAP=50          # per inbox/day (already a constant; confirm or change)
```

### B3. LinkedIn outreach provider — **none integrated today**
- LinkedIn has no official send API; you need a 3rd-party automation provider.
- **Decision:** `[ ] Unipile  ·  [ ] Phantombuster  ·  [ ] HeyReach  ·  [ ] skip LinkedIn for v1 (email only)`
- **You provide (after choosing):** provider API key + the connected **LinkedIn account / session**.
- Fill in:
```
LINKEDIN_PROVIDER=         # unipile | phantombuster | heyreach | none
LINKEDIN_API_KEY=
LINKEDIN_ACCOUNT_ID=       # / session, per provider
```

### B4. The auth gate's `corporate_access_key` (governance, not a vendor key)
- `dispatch_outreach` + contact reads require a valid `corporate_access_key` matching the target contact's
  record (Policy 4). For real sending you need real contact records carrying real keys, or a decision to
  relax/replace this gate for first-party data.
- Fill in / decide:
```
CORPORATE_ACCESS_KEY_SOURCE=   # where real contacts + their keys come from (CRM import? the DB?)
```

---

## C. Operating decisions (no keys — just answers)

| # | Decision | Options / default |
|---|---|---|
| C1 | **Dry-run vs live default** | Default to **dry-run** (compose + log, no real send) until you flip `LIVE_SEND=true`? (recommended) |
| C2 | **Schedule time + timezone** | e.g. **10:00 Asia/Jerusalem**, weekdays only? |
| C3 | **What the daily run does** | `search → analyze → (report) → send`? Or stop before send and queue for approval? |
| C4 | **Approval policy** | Borderline leads → Slack approval (built); do clear-cut leads auto-send, or always require approval first? |
| C5 | **Email copy** | Auto-generate the outreach message with Claude (per lead), or use a fixed template + the ReactFirst report attached? |
| C6 | **Send volume** | Confirm `DAILY_SEND_CAP=50`/inbox; how many inboxes? |
| C7 | **Seed data** | Delete the demo seed (`api_seed.py`) once the real DB has data? (currently the leads/cohorts you see) |

---

## PASTE-BACK BLOCK (fill this and send it to me in one prompt)

```
# --- keys (A) — real values live ONLY in gitignored Backend/.env ---
ANTHROPIC_API_KEY=   # ✅ in Backend/.env
SERPAPI_API_KEY=
TAVILY_API_KEY=
FIRECRAWL_API_KEY=   # ✅ in Backend/.env
SLACK_WEBHOOK_URL=
MONGO_URI=           # mongodb://localhost:27017 (Backend/.env)

# --- ReactFirst (B1) ---
REACTFIRST_BASE_URL=
REACTFIRST_REPORT_PATH=
REACTFIRST_API_KEY=
REACTFIRST_AUTH_SCHEME=

# --- email (B2) ---
EMAIL_PROVIDER=
EMAIL_API_KEY=                 # or SMTP_HOST/PORT/USER/PASS
EMAIL_FROM=
EMAIL_SENDING_DOMAIN=

# --- linkedin (B3) ---
LINKEDIN_PROVIDER=
LINKEDIN_API_KEY=
LINKEDIN_ACCOUNT_ID=

# --- decisions (C) ---
C1_dry_run_default=            # dry-run | live
C2_schedule=                   # e.g. 10:00 Asia/Jerusalem, Mon–Fri
C3_daily_run_scope=            # search→analyze→send | stop-before-send
C4_approval_policy=            # auto-send clear-cut | always approve first
C5_email_copy=                 # claude-generated | template+report
C6_inboxes=                    # how many sending inboxes
C7_drop_seed=                  # yes | no
```
