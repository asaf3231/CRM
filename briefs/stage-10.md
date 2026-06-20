# Brief — Stage 10: Layer 1 — ICP Builder (`build_icp_document`)
Read first: CLAUDE.md → PLAN.md (Stage 10 + Phase 2 section) → QA_checklist.md (§10, `ICPB1`–`ICPB6`) → NOTES.md (2026-06-19 Phase 2 entry), then this brief.

Goal: Add ONE new LLM-callable tool, `build_icp_document`, that turns a seed (company name OR free-text
vertical description) into a **structured ICP document + up to 5 example/anchor companies** — SLED's
Layer-1 4-stage flow (Seed parse → grounded Vertical Research → ICP Synthesis → Example Leads),
re-skinned to our crisis-narrative / brand-safety domain. This takes the tool count **8 → 9**.

## Scope — do ONLY Stage 10
Build the tool, its schema, its dispatch entry, the import-time assert bump, and the tests. Nothing else.
Do **not** start L5/L6, do **not** touch any other tool.

## The contract to build

### Signature & return
```python
def build_icp_document(seed: str) -> dict:
```
Returns a JSON-serializable dict with EXACTLY these keys (ICPB1):
```python
{
  "vertical":         str,         # the inferred/cleaned vertical label
  "want_signals":     list[str],   # ICP "want" qualifiers
  "avoid_signals":    list[str],   # ICP "don't-want" disqualifiers
  "geo":              str,         # geographic focus (or "" / "global")
  "size_band":        str,         # company-size band (free string, e.g. "SMB", "mid-market")
  "icp_tags":         list[str],   # candidate ICP tag labels (see note below)
  "anchor_companies": list[dict],  # <= ICP_ANCHOR_COUNT example leads (ICPB2)
}
```
Each `anchor_companies` item: `{"name": str, "domain": str, "why": str}`.

### Internal 4-stage flow
1. **Seed parse** — accept either a company name or a free-text description; normalize to a vertical
   string. (LIGHT_MODEL or simple heuristic.)
2. **Vertical research (grounded)** — REUSE the existing grounded-search path `_vector_a_search`
   (`main.py:374`, Claude `web_search`) to research the vertical and surface example companies. (Under
   tests this is monkeypatched — see Testing.)
3. **ICP synthesis** — one `_get_client()` Claude call (use `ANALYZER_MODEL` — synthesis is the
   reasoning step) that returns the structured ICP fields as JSON; parse robustly (mirror
   `_parse_query_list`'s tolerant JSON extraction, `main.py:244`).
4. **Example/anchor leads** — take up to `ICP_ANCHOR_COUNT` (=5, already added to Configuration §3)
   example companies **from the grounded research step** (NOT from our catalog). Cap at 5 (ICPB2).

### Hard constraints (these are graded)
- **Import-safe (ICPB3 / ENV4):** no client/model construction at import. Use `_get_client()` lazily
  inside the function, exactly like `generate_search_queries` (`main.py:302`). Wrap the whole body in
  `try/except` and return `{"error": "build_icp_document failed: ..."}` on failure — tool errors are
  data, never crashes (CLAUDE.md §6.6).
- **Anti-leakage (ICPB4 / G2):** NO real `brands_catalog.csv` values (brand names, domains, GTIN, ids,
  tiers) hardcoded in the function or its prompt. Anchors come from runtime research, not literals.
  The tool is **catalog-independent** — it receives no `catalog_df` and must not read the CSV.
- **Policy 2 unchanged (ICPB5):** DO NOT modify `evaluate_icp_tags`, its `_ICP_TAGS` vocabulary
  (`main.py:658`), or the `ICP_TAG_THRESHOLD` ≥3 gate. The `icp_tags` you emit are advisory ICP-doc
  content for the operator/downstream; they do NOT replace the qualification gate. For consistency,
  prefer drawing `icp_tags` values from the SAME label set as `_ICP_TAGS` keys (read it, reuse the
  vocabulary) — but changing `_ICP_TAGS` is out of scope.

### Registration (mechanical)
- Add the function in `main.py` §5 (place it after the 8 core tools, before §6 schemas).
- Add an Anthropic-shaped schema to `TOOL_SCHEMAS` (`main.py:1260`) — same shape as schema 1
  (`name` / `description` / `input_schema`). Description ≥50 chars, state *when to use* (front of a
  discovery task, to define the ICP before query-gen) and the key constraint (≤5 anchors; does not
  qualify leads — that's `evaluate_icp_tags`). Only input property: `seed` (string, required).
- Add `"build_icp_document": build_icp_document` to `TOOL_DISPATCH` (`main.py:1585`).
- **Bump the three import-time asserts from 8 → 9** (`main.py:1598-1603` — both `len(...) == 8` lines).
  The three-way name-identity loop already generalizes; just the counts change.
- In `_SYSTEM_PROMPT_TEMPLATE` (`main.py:2164`), change the hardcoded **"8 tools"** wording to the
  generic **"the tools available to you"** (count-agnostic — avoids churn when Stage 12 adds the 10th).

## Testing — `tests/test_icp_builder.py` (TDD; PM runs them)
You CANNOT run Python in your sandbox — write the tests carefully; the PM runs the full suite.
Mirror the mocking pattern already used in `tests/test_tools.py`:
- Monkeypatch `main._get_client` to a fake whose `.messages.create(...)` returns an object with
  `.content = [SimpleNamespace(text=<canned JSON>)]` and `.stop_reason = "end_turn"`.
- Monkeypatch `main._vector_a_search` to return a canned list of example companies (so no network).
Cover: `ICPB1` (exact key set + JSON-serializable via `json.dumps`), `ICPB2` (≤5 anchors even when the
mock returns 8), `ICPB5` (calling `build_icp_document` does not mutate `main._ICP_TAGS` /
`ICP_TAG_THRESHOLD`), `ICPB6` (two different seeds → both correctly shaped; deterministic under the mock).
`ICPB3` (ENV4) and `ICPB4` (G2) are PM-verified by the existing import-safety + anti-leakage greps —
but add a quick test asserting no exception on a normal call and that `error` is absent on the happy path.

## Constraints from CLAUDE.md that bite here
Import-safety (§3.4), tool errors are data not crashes (§6.6), no catalog literals (§4 / G2), Anthropic
schema shape `{name, description, input_schema}` (§6.7), no raw `eval`/`exec` (irrelevant here but keep
clean). Frameworks permitted but not needed.

## Do NOT
- Advance past Stage 10. Do not touch `evaluate_icp_tags`/`_ICP_TAGS`, the RRF engine, the gateway, or
  any graded literal.
- Inject `catalog_df` into this tool or read the CSV from it.
- Change any tool signature/JSON-schema/policy-constant/loop-contract/graded-literal **other than** the
  sanctioned tool-count bump (8→9) and the generic system-prompt wording. Anything else → surface as
  **DECISION-NEEDED** in your handback and stop.

## Deliver
Write `handbacks/stage-10.md` in the standard format (CLAUDE.md §12): what changed; DoD checklist
(`ICPB1`–`ICPB6`, drafted-only vs written); which tests you wrote; decisions made; deviations; blockers;
one next action. Return it as your final message.
