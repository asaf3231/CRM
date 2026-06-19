# Handback — Stage 9

## 1. What changed

**New files created:**
- `/Users/asaframati/Documents/CRM/tests/test_integration.py` (1453 lines) — integration test suite
- `/Users/asaframati/Documents/CRM/MANIFEST.txt` — explicit shipped-file allowlist (H5)

**Files updated:**
- `/Users/asaframati/Documents/CRM/NOTES.md` — Stage 9 allowlist decision + H2 procedure + INT2/INT3 design decisions appended
- `/Users/asaframati/Documents/CRM/PLAN.md` — Stage 9 status updated to "Awaiting verification"

**No shipped code changed** (main.py, lead_store.py, rag_engine.py, requirements.txt, angle_corpus.json all untouched — packaging artifacts are additive only per the brief).

### tests/test_integration.py — test structure

| Class | Tests | QA IDs |
|---|---|---|
| `TestINT1SubdomainRouting` | 5 tests | INT1 |
| `TestINT2MultiChannelInterop` | 5 tests | INT2 |
| `TestINT3IdempotentRerun` | 3 tests | INT3 |
| `TestH1PinnedDependencies` | 4 tests | H1 |
| `TestH3ImportSafety` | 4 tests | H3 |
| `TestH4IdentityHeader` | 3 tests | H4 |
| `TestH5Manifest` | 5 tests | H5 |

Total new tests: ~29.

### MANIFEST.txt — shipped allowlist

Explicit shipped files:
```
main.py
lead_store.py
rag_engine.py
requirements.txt
angle_corpus.json
```

Excluded (dev-only / generated / secret-bearing): `tests/`, `Reference/`, the PRD PDF, all working `.md` files (`CLAUDE.md`/`PLAN.md`/`QA_checklist.md`/`NOTES.md`/`ORCHESTRATION.md`/`PM_Methodology_Prompt.md`), `briefs/`, `handbacks/`, `.chroma/`, `assets/`, `.venv/`, `.DS_Store`, `reactfirst_run.log`, `qualified_leads.json`.

Runtime input fixtures excluded by default: `brands_catalog.csv`, `contacts.json`, `gtm_policies.txt` (grader provides at runtime — G5 generalization property).

---

## 2. DoD checklist

| QA ID | Status | Verification method |
|---|---|---|
| `INT1` | ⚠️ Drafted only | Static AST grep of main.py + lead_store.py + rag_engine.py for OUTREACH_SUBDOMAIN references; behavioral check of pure tools (T5, T8, T3); 5 test methods in `TestINT1SubdomainRouting`. PM must run. |
| `INT2` | ⚠️ Drafted only | Auth-gate valid/no/wrong-key sub-tests (INT2a/b/c); full mocked run with call counters verifying all 8 components touched + no secret in log + GW4 PDF health (INT2d/e). PM must run. |
| `INT3` | ⚠️ Drafted only | Two identical runs → equal `qualified_leads.json` content (INT3a); same PDF filename overwritten not duplicated (INT3b); `seed_corpus_if_empty` idempotency via DB guard (INT3c). PM must run. |
| `H1` | ⚠️ Drafted only | AST-extracts imports from 3 shipped modules; checks each against `requirements.txt`; verifies `==` pinning and no openai/google-genai. PM must run. |
| `H2` | ⚠️ Drafted only — PM runs | Procedure documented in NOTES.md: `pip install -r requirements.txt && python -c "import main..." && python main.py "<query>"`. PM verifies pragmatic H2 in its `.venv`. |
| `H3` | ⚠️ Drafted only | In-process lazy-singleton checks + subprocess ENV4 round-trip (launches fresh Python subprocess with no API keys, no input files → import must exit 0). PM must run. |
| `H4` | ⚠️ Drafted only | AST parse of main.py header; checks `Author:` line, `ReactFirst` project identity, `Import-safe` guarantee in docstring. PM must run. |
| `H5` | ⚠️ Drafted only | MANIFEST.txt created; test checks required files present, excluded files absent, relative paths only, no PDFs or .env files. PM must run. |

All checks are **drafted only** — the executer's sandbox cannot run Python/pytest. The PM verifies every check.

---

## 3. QA results

**No QA checks were run** — this sandbox cannot execute Python. All tests are drafted only.

The PM must run:
```bash
cd /Users/asaframati/Documents/CRM
.venv/bin/python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: 461 (baseline) + ~29 new tests = ~490 passed, 1 skipped.

---

## 4. Decisions made

1. **H5 allowlist default** — `brands_catalog.csv`, `contacts.json`, `gtm_policies.txt` excluded from MANIFEST.txt. The brief says "grader provides runtime data"; the engine loads whatever is in cwd at runtime (G5). Documented in NOTES.md and MANIFEST.txt comments.

2. **INT2 auth-gate fixture keys** — Used synthetic keys `IntKeyValidAlpha001` / `IntKeyValidBeta002` (not the real `contacts.json` keys) to maintain G4 cleanliness in tracked test files. Pattern follows Stage-8 PM fix for `test_lead_store.py`.

3. **INT3c idempotency test approach** — Tests the DB guard (`collection.count() > 0`) by resetting only the in-memory `_corpus_seeded` flag while the collection stays populated. This proves the cross-session guard (not just the per-session flag).

4. **INT1 AST approach** — Uses `ast.NodeVisitor` to find function definitions that reference `OUTREACH_SUBDOMAIN` or the literal `"outreach.reactfirst.ai"`. Tolerates `_check_pdf_health` (gateway helper) as an allowed function alongside `request_reactfirst_pdf`.

5. **H3 subprocess test** — Spawns a fresh subprocess (no API keys, tmp cwd, no input files) that imports all 3 modules and asserts lazy singletons are None. This is the strongest ENV4 proof on the final tree.

6. **H2 procedure** — Written in NOTES.md as a runnable bash procedure. The PM verifies pragmatically in `.venv` (not a full fresh-venv re-install, since ENV1 was proven at Stage 1 and deps are unchanged).

---

## 5. DECISION-NEEDED

None. All decisions were covered by the brief's documented defaults:
- Allowlist excludes runtime fixtures (documented default per brief).
- No tool signatures, schemas, policy constants, loop contract, or graded literals changed.

---

## 6. Deviations

None. The stage's scope is exactly as specified in the brief:
- `tests/test_integration.py` created (INT1–INT3, H1, H3, H4, H5)
- `MANIFEST.txt` created (H5)
- NOTES.md + PLAN.md updated
- No shipped code changed

---

## 7. Blockers / risks

1. **INT3c singleton isolation** — The test saves and restores `rag_engine._collection_instance` and `_corpus_seeded`. If another test runs concurrently and modifies these globals, INT3c could flake. Pytest is single-threaded by default; this is safe in serial runs.

2. **INT2a/b/c `tmp_path` sharing** — `tmp_cwd` and `tmp_contacts_json` both use pytest's function-scoped `tmp_path`. Pytest guarantees the same `tmp_path` instance within a test, so contacts.json is written to cwd. If pytest changes this behavior, the tests could break.

3. **H1 import detection** — The `_extract_imports` helper uses `ast.walk` and catches all import statements including lazy ones inside functions. This is intentional: all lazy imports (`import anthropic` inside `_get_client()`) are captured. The stdlib exclusion set is broad but may miss an unusual stdlib module. If a new stdlib module is imported in a future edit, the check may falsely flag it.

4. **Full regression baseline** — The new ~29 tests must pass alongside the existing 461 (baseline). No existing tests were modified; the new tests are additive.

---

## 8. Next recommended action

**PM runs the full regression in `.venv`:**
```bash
.venv/bin/python -m pytest tests/ -v 2>&1 | tail -30
```

Expected outcome: ~490 passed, 1 skipped (S10), 0 failed.

If all checks pass → Stage 9 ✅ → **project complete** (all 9 stages done).

If a test fails, the PM either auto-retries (1st consecutive failure) or halts to Asaf (2nd consecutive failure on this stage).

---

**Overall project-completion readiness:**

Stages 1–8 are all ✅ PM-verified with a full-regression baseline of **461 passed, 1 skipped, 0 failed**. The pipeline:
- Runs end-to-end (E1–E4 verified)
- Generalizes to new verticals (G5 verified — no hardcoded seeds)
- Is anti-leakage clean (G1–G4 verified by PM greps)
- Has all 8 tools with correct contracts (T1–T8 verified)
- Has full governance (Policies 1–6, Trust-Gate, Gateway — POL1/POL2/PR1-PR4/CL1-CL4/TG1-TG2/FB1-FB4/GW1-GW5 verified)
- Has hybrid RAG/RRF (RAG1–RAG5, T6.* verified)
- Has the import-safety contract (ENV4 verified)
- Has no forbidden frameworks or raw eval (G1/L5 grep-clean)

Stage 9 (this stage) adds multi-channel integration tests (INT1–INT3) and packaging hygiene (H1–H5). Once the PM verifies these pass, the project is complete.
