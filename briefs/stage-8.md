# Brief — Stage 8: Generalization & anti-leakage hardening
Read first: CLAUDE.md (§10 quality rules, §5 anti-leakage, Policy 1) → PLAN.md → QA_checklist.md (§8) → NOTES.md, then this brief.

Goal: Prove the engine generalizes to a NEW vertical with no code change, and that it leaks no
secrets, sample/catalog data, raw eval, or framework. This is the highest-leverage correctness gate —
treat any hardcoded sample value or stray secret as a blocker to FIX, not just report.

## Context you must know (settled — do not relitigate)
- **Stages 1–7 are ✅ PM-verified.** Full-regression baseline: **438 passed, 1 skipped (S10)**. The
  full pipeline runs end-to-end (E1–E4 verified) producing `qualified_leads.json` + `reactfirst_run.log`
  + `assets/*.pdf`.
- The 3 runtime fixtures (`brands_catalog.csv`, `contacts.json`, `gtm_policies.txt`) are **gitignored**;
  `angle_corpus.json` is an internal RAG asset. `corporate_access_key` values (e.g. `Access99`,
  `Cobalt7Key`, …) live ONLY in the gitignored `contacts.json` + env — they must appear in **no tracked
  code file**.
- Shipped modules: `main.py`, `lead_store.py`, `rag_engine.py` (+ `requirements.txt`, `angle_corpus.json`).
  `tests/` and the `.md`/`Reference/` files are dev-only (not shipped) — but G1/G4 still must be clean
  there for secrets/eval.

## Scope (do ONLY this stage)
- **`tests/test_generalization.py`** — the G-checks, test-first:
  - **G5 (the headline):** drive the full pipeline end-to-end with a **second, DIFFERENT synthetic
    vertical seed** than Stage 7 used (e.g. a different `Core_Category` family), all services mocked via
    `FakeReasoningClient` + mocks, in a `tmp_path` cwd. Assert correct artifacts (`qualified_leads.json`
    ≤3, a GW4-valid PDF, the run log) are produced **with NO code change** — proving behavior is driven
    by the inputs, not by a branch on a specific seed/brand. Use synthetic fixtures only (no real
    catalog values).
  - **G1:** grep all `*.py` for raw `eval(`/`exec(` and for framework/tool-runner tokens
    (`langgraph|langchain|create_react_agent|AgentExecutor|bind_tools|tool_runner|beta_tool`) → **zero
    hits** (the only `ast` use is the `secured_calculator` whitelist walker).
  - **G2:** grep the **shipped** modules (`main.py`, `lead_store.py`, `rag_engine.py`) + `angle_corpus.json`
    for any real catalog literal (brand name / `Primary_Domain` / `Gtin_Prefix` / `Uniq_Id` /
    `Main_Competitor_Id` / a real tier-or-status value used as a *seed*), read from the actual
    `brands_catalog.csv` at test time → **zero hits**. (Reuse the CAT5 pattern; extend to `rag_engine.py`
    + the corpus.)
  - **G3:** grep shipped modules for **hardcoded absolute paths** (`C:\\`, a leading `/Users/`, `/home/`,
    `/private/`) → none; paths are built with `os.path`/`pathlib` relative to cwd. (Runtime-resolved
    absolute paths via `os.getcwd()` are fine — only *hardcoded* literals fail.)
  - **G4:** grep **all tracked files** (`*.py`, `*.json` except the gitignored fixtures, `requirements.txt`)
    for the `corporate_access_key` values (read from `contacts.json` at test time) and for generic
    key/token patterns (`api[_-]?key\s*=\s*["'][A-Za-z0-9]`, `sk-`, `Bearer `, hardcoded webhook URLs) →
    **zero hits**; all secrets come from `os.environ`.
- **Hardening:** if any G1–G4 grep finds a hit in shipped code, **FIX it** (genericize the literal, move
  the secret to `os.environ`, relativize the path) and note the fix. A hit is a blocker, not a warning.

## QA checks to PASS (run, not inspect — by the PM)
`G1`, `G2`, `G3`, `G4`, `G5`. **Your sandbox cannot run Python** — write the tests + apply any
hardening fixes, mark *drafted only*; the PM re-runs every grep itself + the G5 second-vertical E2E +
the full regression.

## Constraints (from CLAUDE.md that bite this stage)
- Behavior must be driven by the three inputs + the query — **no branch on a specific seed/brand/domain**
  anywhere in shipped code (G5/G2). The G5 seed must differ from Stage 7's.
- Import-safety (ENV4) holds. ≤3 ceiling, byte-exact `FALLBACK_MESSAGE`, GW4 PDF health, single-egress
  subdomain — all still enforced (don't regress them). Keep the full regression green (438/1 baseline,
  +the new G5 tests).
- Do NOT change a tool signature / schema / policy constant / the loop contract / a graded literal.
  Hardening edits are limited to removing leaked literals / relativizing paths / moving secrets to env.

## Inputs / files you may touch
Create/edit: `tests/test_generalization.py`; and ONLY-IF-a-leak-is-found, the offending shipped file
(`main.py`/`lead_store.py`/`rag_engine.py`/`angle_corpus.json`) to remove the leak. Do NOT alter tool
logic, schemas, governance helpers, or the loop beyond a leak fix.

## Do NOT
Advance past Stage 8. Change a tool signature / schema / policy constant / loop contract / graded
literal. If a "leak" is actually a required literal (e.g. a model id, the `OUTREACH_SUBDOMAIN`, the
`FALLBACK_MESSAGE`) — those are intended and NOT leaks; do not remove them. If unsure whether something
is a leak, surface **DECISION-NEEDED** rather than delete a contractual literal.

## Deliver
Write `handbacks/stage-8.md` in the standard format; separate *drafted only* from *written and
test-verified*; list every `G*` check + any hardening fix applied. Return it as your final message.
