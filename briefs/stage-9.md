# Brief — Stage 9 (FINAL): Multi-channel integration testing & packaging
Read first: CLAUDE.md (§2 layout, §5 envelopes/subdomain, §10 quality rules, §11 completion) → PLAN.md → QA_checklist.md (§7 INT, §9 H) → NOTES.md, then this brief.

Goal: Prove all components interoperate end-to-end (catalog + store + RAG + crawler + PDF + gateway),
honor the subdomain single-egress + auth-gate constraints, and package the deliverable cleanly from an
explicit allowlist.

## Context you must know (settled — do not relitigate)
- **Stages 1–8 are ✅ PM-verified.** Full-regression baseline: **461 passed, 1 skipped (S10)**. The
  pipeline runs end-to-end (E1–E4), generalizes to a new vertical (G5), and is anti-leakage clean (G1–G4).
- Shipped modules: `main.py`, `lead_store.py`, `rag_engine.py`, `requirements.txt`, `angle_corpus.json`
  (internal RAG asset). Dev-only (NOT shipped): `tests/`, `Reference/`, the PRD PDF, the working `.md`
  files (`CLAUDE.md`/`PLAN.md`/`QA_checklist.md`/`NOTES.md`/`ORCHESTRATION.md`/`PM_Methodology_Prompt.md`),
  `briefs/`, `handbacks/`, `.chroma/`, `assets/`, `.venv/`, the 3 gitignored input fixtures, `.DS_Store`.
- `OUTREACH_SUBDOMAIN = "outreach.reactfirst.ai"`; only `request_reactfirst_pdf` may egress there.
- `main.py` already carries an author/identity header block (H4) and the lazy singletons (H3/ENV4).

## Scope (do ONLY this stage)
- **`tests/test_integration.py`** — INT1–INT3, all mocked, zero network:
  - **INT1 single-egress:** assert **only** `request_reactfirst_pdf` references `OUTREACH_SUBDOMAIN`
    (grep shipped modules + a behavioral check that no other tool's path targets the subdomain).
  - **INT2 multi-channel interop:** one mocked run that touches catalog (load + filter) + `lead_store`
    (an **auth-gated contact read** — a valid-key read succeeds, and assert no contact field is exposed
    via a missing/invalid key) + RAG (`match_solicitation_angle`) + crawler (`analyze_company_chunk`
    mocked) + PDF (`request_reactfirst_pdf` mocked) + gateway — all interoperating; **no secret leaked**
    in artifacts/logs.
  - **INT3 idempotent re-run:** run the same scripted input **twice** → identical qualified set /
    `qualified_leads.json` content; no duplicate/corrupt assets in `assets/`; Chroma corpus **reused**
    (seed is idempotent), not blindly rebuilt.
- **Packaging (H5) — explicit allowlist, never zip-the-directory:** add a `MANIFEST.txt` (or a small
  `build_bundle.py` that copies from an allowlist) enumerating exactly the shipped files:
  `main.py`, `lead_store.py`, `rag_engine.py`, `requirements.txt`, `angle_corpus.json`, and a short
  `README` if you add one. It MUST exclude everything dev-only listed above. Document the allowlist in
  NOTES. (Whether the 3 runtime input fixtures ship is the grader's data — default: exclude the
  gitignored synthetic fixtures; the engine loads whatever is in cwd at runtime. Document this.)
- **H1/H3/H4 audits** (write as asserts in `tests/test_integration.py` or a small `tests/test_packaging.py`):
  H1 — every non-stdlib import in the shipped modules is pinned `==` in `requirements.txt` (reuse the
  ENV2 pattern); H3 — `import main, lead_store, rag_engine` is side-effect-free on the final tree
  (ENV4 cross-check); H4 — `main.py` top comment carries the author/identity block.

## QA checks to PASS (run, not inspect — by the PM)
`INT1`, `INT2`, `INT3`, `H1`, `H3`, `H4`, `H5`. `H2` (fresh-venv install → `import main` → `python
main.py` runs without traceback): write the procedure; the **PM** runs a pragmatic H2 (`python main.py
"<query>"` runs without an uncaught traceback — ENV1 fresh-install was already proven at Stage 1 and
deps are unchanged). **Your sandbox cannot run Python** — mark *drafted only*; the PM runs everything.

## Constraints (from CLAUDE.md that bite this stage)
- Single egress: only `request_reactfirst_pdf` → `OUTREACH_SUBDOMAIN` (INT1). Auth gate is the sole
  contact chokepoint (INT2). ≤3 ceiling, byte-exact `FALLBACK_MESSAGE`, GW4 PDF health — unchanged.
- No secrets in tracked/shipped files (G4 stays clean); secrets via `os.environ`. No `eval`/framework.
- Import-safety holds on the final tree (H3/ENV4). OS-agnostic paths. Keep the full regression green
  (461/1 baseline + new tests).
- Do NOT change a tool signature / schema / policy constant / the loop contract / a graded literal.
  Packaging artifacts (MANIFEST/build script/README) are additive only.

## Inputs / files you may touch
Create/edit: `tests/test_integration.py` (+ optional `tests/test_packaging.py`), `MANIFEST.txt` or
`build_bundle.py`, optional `README.md` (shipped), and the NOTES allowlist entry. Do NOT alter tool
logic, schemas, governance, the loop, or `lead_store.py`/`rag_engine.py` behavior.

## Do NOT
Change a tool signature / schema / policy constant / loop contract / graded literal. If the shipped-file
allowlist or whether the input fixtures ship needs an Asaf decision, pick the documented default
(ship code + requirements + `angle_corpus.json`; exclude fixtures/dev files) and note it; STOP +
DECISION-NEEDED only on a genuine conflict.

## Deliver
Write `handbacks/stage-9.md` in the standard format; separate *drafted only* from *written and
test-verified*; list every `INT*`/`H*` check + the H5 allowlist. This is the final stage — note overall
project-completion readiness. Return it as your final message.
