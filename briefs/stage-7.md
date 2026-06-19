# Brief — Stage 7: End-to-end single-vertical run
Read first: CLAUDE.md (§3 runtime contract, §3.1 happy path, §3.2 I/O) → PLAN.md → QA_checklist.md → NOTES.md, then this brief.

Goal: Drive the full pipeline end-to-end on one vertical seed (all external services mocked),
confirming artifacts, the call cap, the Vector-C recovery path, and the Policy-6 fallback.

## Context you must know (settled — do not relitigate)
- **Stages 1–6 are ✅ PM-verified.** Full-regression baseline: **428 passed, 1 skipped (S10)**. The
  8 tools, schemas/dispatch, the raw loop (`answer_question`, 15-call cap, resiliency, metrics,
  dual-write `reactfirst_run.log`), the governance/gateway/Policy-6 terminal, and the hybrid RAG/RRF
  angle engine all work and are verified.
- **No `ANTHROPIC_API_KEY`** on this machine — the E2E run CANNOT make live LLM calls. Drive
  `answer_question` with a **`FakeReasoningClient`** (reuse/extend the one in `tests/test_loop.py` or a
  conftest) that scripts a realistic multi-turn tool sequence, and patch the external services
  (Vector A/B/C, Firecrawl, ReactFirst, Slack) with mocks. **Zero network.**
- `request_reactfirst_pdf` already saves a health-valid PDF under `assets/` (Stage 2, GW4-checked).
  `dual_log` already writes `reactfirst_run.log`. Per-tool + total call metrics are tracked (RS4).

## Scope (do ONLY this stage)
- **Wire the `qualified_leads.json` artifact** (CLAUDE.md §3.1 happy path ends here; §3.2 step 4). On a
  discovery run that produces qualified leads, write `qualified_leads.json` to cwd (built with
  `os.path`/`pathlib`), containing the qualified leads with their angle/tier/domain, **capped at ≤3
  angles total (Policy 5 — route through `cap_angles`/the gateway)**. Add a small helper (e.g.
  `write_qualified_leads(...)`); call it from `answer_question`'s success terminal or `main()`. Do NOT
  restructure the loop contract; this is an output-artifact addition only.
- **`tests/test_e2e.py`** — driven end-to-end via `answer_question` (monkeypatch `main._get_client` →
  `FakeReasoningClient`; patch the vector/crawler/PDF/Slack mocks). Cover:
  - **E1 happy path:** a discovery seed that qualifies ≥1 brand → `qualified_leads.json` +
    `reactfirst_run.log` produced; **≤3 angles**; **≥1 saved PDF that passes the GW4 health check**
    (`%PDF-`/non-zero/`%%EOF`). Use a `tmp_path`/`monkeypatch.chdir` so artifacts land in a throwaway dir.
  - **E2 within the cap:** total tool calls **≤15** with headroom; metrics present in the log + result.
  - **E3 recovery path:** script the fan-out so `A∪B < 2` distinct domains → **Vector C fires**
    (call-spy) and the pipeline still completes end-to-end.
  - **E4 fallback path:** a **no-match seed** (all `evaluate_icp_tags` → `qualified=False`, or all
    angles Tier 4) driven end-to-end → the result is **exactly `FALLBACK_MESSAGE`** and nothing else;
    the generative path is bypassed (no apology LLM call — FB4 cross-check); **no `qualified_leads.json`
    written** on a pure no-match (or it is written empty/with the fallback — your call, document it).
- The run must work from **generic runtime reasoning over the inputs** — **do NOT hardcode the seed,
  a brand, or a domain** into `main.py` (Stage 8/G5 re-checks this; a hardcoded seed is a blocker).

## QA checks to PASS (run, not inspect — by the PM)
`E1`, `E2`, `E3`, `E4`. **Your sandbox cannot run Python** — write the artifact-writer + `tests/test_e2e.py`,
mark *drafted only*; the PM runs them + the full regression in `.venv`.

## Constraints (from CLAUDE.md that bite this stage)
- No live LLM/network/crawl — all mocked. No `ANTHROPIC_API_KEY` reliance in tests.
- Import-safety (ENV4) holds — the artifact writer opens files only when called, never at import.
- ≤3 angles enforced at the output boundary (Policy 5 / gateway). Byte-exact `FALLBACK_MESSAGE` on
  no-match. PDFs pass GW4. Only `request_reactfirst_pdf` egresses to `OUTREACH_SUBDOMAIN`.
- No hardcoded seed/brand/domain/catalog values (CAT5/G2/G5). OS-agnostic paths. No `eval`/framework.
- Keep the full regression green (428/1 baseline). Do NOT change a tool signature, schema, policy
  constant, the loop contract, or a graded literal.

## Inputs / files you may touch
Create/edit: `main.py` (a `write_qualified_leads` helper + its call site in the success terminal /
`main()` — minimal), `tests/test_e2e.py` (+ optional conftest additions for shared fakes). Do NOT edit
the §5 tools' logic, §6/§7 schemas, §8 governance helpers, `lead_store.py`, `rag_engine.py`, or
`angle_corpus.json`.

## Do NOT
Advance past Stage 7. Change a tool signature / schema / policy constant / the loop contract / a graded
literal. If `qualified_leads.json`'s exact shape or the no-match artifact behavior needs an Asaf
decision, pick a sensible default, document it in NOTES, and proceed (only STOP+DECISION-NEEDED if a
genuine contract conflict arises).

## Deliver
Write `handbacks/stage-7.md` in the standard format; separate *drafted only* from *written and
test-verified* (all drafted-only — PM verifies). List every `E*` check covered. Return it as your final message.
