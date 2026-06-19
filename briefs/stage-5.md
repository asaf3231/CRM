# Brief — Stage 5: Governance — policies, trust-gate & tool gateway
Read first: CLAUDE.md (§5 all policies + §8 layout) → PLAN.md → QA_checklist.md → NOTES.md, then this brief.

Goal: Implement the governance policies (1, 2, 3, 5, 6 + Trust-Gated Autonomy; Policy 4 already
lives in `lead_store.py`) and harden the single Tool Gateway chokepoint — each enforced at the
output boundary, each test-driven.

## Context you must know (settled — do not relitigate)
- **Stages 1–4 are ✅ PM-verified.** Full-regression baseline: `tests/` = **277 passed, 1 skipped
  (S10)**. The agentic loop (§10) already routes every outbound payload through `gateway_validate`
  (§8), which is currently a **permissive pass-through stub** — Stage 5 hardens it **in place** (keep
  the call sites). The loop's termination precedence already has a hook to return `FALLBACK_MESSAGE`
  on a terminal zero-match/validation signal — Stage 5 wires the actual detection.
- Constants already exist in §3: `MAX_ANGLES=3`, `ICP_TAG_THRESHOLD=3`, `PREMIUM_MULTIPLIER=1.15`,
  `INCIDENT_PREMIUM_THRESHOLD=5`, `FALLBACK_MESSAGE`, `_RE_DOMAIN`/`_RE_ANGLE_KEY`/`_RE_TIER_LABEL`,
  `OUTREACH_SUBDOMAIN`. The `_SYSTEM_PROMPT_TEMPLATE` exists (§3/§10).
- **OQ-5 (Policy 3 base value) is NOT a halt** — Asaf's recorded default: `secured_calculator`
  evaluates whatever base the caller/context supplies; Q1 answers qualitatively + numerically when a
  base is present. Build against that default.

## Scope (do ONLY this stage) — implement in `main.py` §8 (+ minimal §10 wiring / §3 prompt)
- **Tool Gateway `gateway_validate(payload)` (GW1–GW5)** — replace the stub with the real validator,
  a single chokepoint:
  - GW1: reject null/None payload or empty required field → **structured rejection** dict (no raise,
    no send).
  - GW2: enforce format regexes — domain shape (`_RE_DOMAIN`), `angle_key` shape (`_RE_ANGLE_KEY`),
    tier label (`_RE_TIER_LABEL`); malformed value rejected. (Record the exact patterns in NOTES.)
  - GW3: every rejection is structured data fed back to the loop, never an uncaught exception.
  - GW4: **PDF health** — for a saved asset, require `%PDF-` magic header, non-zero length, and a
    `%%EOF` marker; a truncated/empty PDF is rejected.
  - GW5: re-enforce the Policy 5 ≤3 ceiling as the **last line of defense**.
- **Policy 5 ceiling `cap_angles(...)` (CL1–CL4)** — net rule `output_count = min(requested or 3, 3)`:
  CL1 no count → exactly 3 (when >3 available); CL2 "top 5"/N>3 → capped to **exactly 3**, no error,
  **record an override flag**; CL3 "top 2"/subset ≤3 → **exactly that count**, no padding; CL4 enforced
  at the output boundary (gateway) so no upstream path can exceed 3. (You may add a small helper to
  parse a requested count from the query text.)
- **Policy 6 fallback (FB1–FB4)** — `FALLBACK_MESSAGE` is byte-exact (already a constant; do not
  alter it). Wire the loop terminal so that **zero qualifying matches** (all leads fail
  `evaluate_icp_tags`, or all map to Tier 4) **or** a hard stage-validation failure returns **only**
  the fallback string — no JSON wrapper, no LLM prose. **The generative path must be bypassed** (do
  NOT call the reasoning client to compose an apology — FB4 spies on exactly this). Add a small
  helper (e.g. `is_zero_match(...)`/`policy6_fallback(...)`); lightly extend `answer_question`'s
  terminal **without restructuring the loop contract / precedence**.
- **Policy 3 premium loop `apply_premium(base_value, tier, incidents)` (PR1–PR4)** —
  PR1: `tier == "Tier 1"` → premium/enterprise-SLA eligible; non-Tier-1 not (tier from the CSV,
  never invented — Policy 1). PR2: `incidents > INCIDENT_PREMIUM_THRESHOLD (=5)` strictly → apply the
  15% (`PREMIUM_MULTIPLIER`); at `==5` and `<5` do **not** (boundary-tested). PR3: compute via
  **`secured_calculator`** only — `secured_calculator(f"{base_value} * 1.15")` — never raw eval/exec.
  PR4 (integration): a Q1-style query routes authenticate (`lead_store`) → `get_lead_data_collection`
  → read tier+incidents → `secured_calculator` → report the premium tier; tier/incidents sourced from
  the catalog/record only.
- **Policy 1 (POL1)** — ensure `_SYSTEM_PROMPT_TEMPLATE` forbids asserting any brand market-position/
  tier/competitor fact not present in `brands_catalog.csv` (retrieved/quoted, never generated). Cross-
  check `CAT5`/`G2` (no hardcoded catalog values — keep it clean; CAT5 just got fixed).
- **Policy 2 (POL2)** — the **only** qualification gate is `evaluate_icp_tags` returning `count >= 3`;
  no other code path may mark a brand qualified. Enforce/assert this in the qualification path.
- **Trust-Gated Autonomy `route_prospect(...)` (TG1–TG2)** — a **borderline** prospect (exactly 3 ICP
  tags + low secondary indicators) is **not** auto-emailed; route it to a **Slack webhook** (mocked in
  tests) for human approval; clear-cut (≥4 tags, or 3 with strong indicators) proceeds autonomously.
  TG2: the Slack webhook URL is an **env secret** (`os.environ`, pick a var name e.g.
  `SLACK_WEBHOOK_URL` and record it in NOTES); routing is logged **without** leaking the URL. Decide
  and record the borderline "low indicator" thresholds in NOTES (a Stage-5 decision, like the ICP
  vocab).
- **`tests/test_policies.py`** — cover POL1, POL2, PR1–PR4, CL1–CL4, TG1–TG2, FB1–FB4, GW1–GW5. Use
  the §0 fixtures (`tmp_catalog_csv`, `seeded_lead_store`, `MockSlack`, `MockReactFirst`,
  `FakeReasoningClient`). FB4 must spy that the reasoning client is **not** asked to compose the
  fallback. PR2 must boundary-test `incidents` at 4/5/6. No live network.

## QA checks to PASS (run, not inspect — by the PM)
`POL1`, `POL2`, `PR1`–`PR4`, `CL1`–`CL4`, `TG1`–`TG2`, `FB1`–`FB4`, `GW1`–`GW5`. **Your sandbox cannot
run Python** — write the tests, mark *drafted only*; the PM runs them + the full regression in `.venv`.

## Constraints (from CLAUDE.md that bite this stage)
- Each policy is a **single chokepoint** — no scattering. Any path that bypasses the gateway is a blocker.
- `FALLBACK_MESSAGE` is the ONE byte-exact literal — do not change it; the fallback is never produced
  by asking a model to apologize.
- Policy 3 pricing math goes through `secured_calculator` ONLY — **no raw `eval`/`exec`** (grep clean).
- Secrets (Slack webhook) via `os.environ` only — never hardcoded, never in logs/payloads/tracked files.
- No catalog values hardcoded (CAT5/G2 must stay clean). No framework imports.
- Import-safety (ENV4) holds — helpers define logic only; no client/secret access at import.
- Do NOT change a tool signature, JSON schema, policy constant, the loop **contract/precedence**, or a
  graded literal. Do NOT touch §5 tool bodies, §6/§7 schemas, or `lead_store.py`'s gate (call it, don't
  edit it). Lightly extend `answer_question` only to wire the Policy-6 terminal + gateway ≤3 boundary.

## Inputs / files you may touch
Create/edit: `main.py` §8 (`gateway_validate` hardening, `cap_angles`, `apply_premium`, the Policy-6
helper, `route_prospect`), minimal §10 wiring, §3 `_SYSTEM_PROMPT_TEMPLATE` (Policy 1/2 language);
`tests/test_policies.py`. Do NOT edit the §5 tools, §6/§7, §4 loader, `lead_store.py`, `rag_engine.py`.

## Do NOT
Advance past Stage 5. Change a tool signature / JSON schema / policy constant / loop contract /
graded literal. If Policy 3's base value (OQ-5) seems to need a value beyond Asaf's caller-supplied
default, or any other unspecified decision arises, STOP and surface **DECISION-NEEDED**.

## Deliver
Write `handbacks/stage-5.md` in the standard format; separate *drafted only* from *written and
test-verified* (all drafted-only — PM verifies). List every check covered. Return it as your final message.
