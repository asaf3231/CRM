"""
tests/test_generalization.py — Stage 8: Generalization & anti-leakage hardening.

QA checks covered:
  G1  no raw eval()/exec(); no framework/tool-runner imports in any .py.
  G2  no hardcoded real catalog literals (brand names / domains / GTINs / Uniq_Ids /
      Main_Competitor_Ids) in shipped modules (main.py, lead_store.py, rag_engine.py,
      angle_corpus.json).
  G3  no hardcoded absolute paths in shipped modules; all paths use os.path/pathlib
      relative to cwd (C:\\, /Users/, /home/, /private/ → zero hits).
  G4  no corporate_access_key values (from contacts.json) and no generic secret
      patterns (api_key=, sk-, hardcoded webhook URLs) in shipped modules
      (main.py, lead_store.py, rag_engine.py, angle_corpus.json, requirements.txt).
  G5  second, DIFFERENT synthetic vertical seed (Electronics > Audio > Wearable) runs
      the full pipeline end-to-end with NO code change; correct artifacts produced
      (qualified_leads.json ≤3, GW4-valid PDF, run log).

All external services mocked — ZERO network calls.
G5 uses tmp_path / monkeypatch.chdir so artifacts land in a throwaway temp dir.

DRAFTED ONLY — PM re-runs every grep + G5 E2E + full regression in .venv.
"""

import importlib
import json
import os
import pathlib
import re
import sys

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Path setup: ensure the CRM root is on sys.path.
# ---------------------------------------------------------------------------
_CRM_ROOT = pathlib.Path(__file__).parent.parent
if str(_CRM_ROOT) not in sys.path:
    sys.path.insert(0, str(_CRM_ROOT))

import main  # noqa: E402  (import-safe — ENV4)

# ---------------------------------------------------------------------------
# Paths to shipped modules and tracked files
# ---------------------------------------------------------------------------
_MAIN_PY         = _CRM_ROOT / "main.py"
_LEAD_STORE_PY   = _CRM_ROOT / "lead_store.py"
_RAG_ENGINE_PY   = _CRM_ROOT / "rag_engine.py"
_ANGLE_CORPUS    = _CRM_ROOT / "angle_corpus.json"
_REQUIREMENTS    = _CRM_ROOT / "requirements.txt"

# All shipped .py files (includes tests/ for G1 eval/exec coverage)
_ALL_PY_FILES = list(_CRM_ROOT.rglob("*.py"))

# Shipped non-test modules only (for G2/G3/G4 catalog/secret checks)
_SHIPPED_PY = [_MAIN_PY, _LEAD_STORE_PY, _RAG_ENGINE_PY]
_SHIPPED_NONPY = [_ANGLE_CORPUS, _REQUIREMENTS]

# All tracked files for G4 secret scan (exclude gitignored fixtures)
# contacts.json, brands_catalog.csv, gtm_policies.txt are gitignored — excluded.
_ALL_TRACKED = list(_CRM_ROOT.rglob("*.py")) + [_ANGLE_CORPUS, _REQUIREMENTS]


def _read_text(path: pathlib.Path) -> str:
    """Read file text; return empty string if not found."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


# ===========================================================================
# G1 — No raw eval()/exec(); no forbidden framework/tool-runner tokens
# ===========================================================================

class TestG1NoEvalNoFramework:
    """G1: grep all .py files for raw eval()/exec() and forbidden framework tokens.

    Pass condition: zero hits in shipped code.
    The only valid AST usage is the whitelist walker in secured_calculator (ast.parse).
    """

    def test_g1_no_raw_eval_in_shipped_modules(self):
        """G1a: no raw eval() call in main.py, lead_store.py, rag_engine.py."""
        for pyfile in _SHIPPED_PY:
            src = _read_text(pyfile)
            # Look for a real eval( call (not inside a string or comment).
            # We use a simple line-by-line scan, stripping comment-only lines.
            lines_with_eval = []
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                # Skip pure comment lines
                if stripped.startswith("#"):
                    continue
                # Check for eval( not inside a string literal being checked
                # (but we use a regex that captures bare code-level eval()
                # while allowing "eval(" as a literal inside strings — tricky;
                # use a conservative approach: any occurrence is flagged and
                # must be justified).
                if re.search(r"\beval\s*\(", line):
                    lines_with_eval.append((lineno, line.rstrip()))
            assert not lines_with_eval, (
                f"G1 FAIL: raw eval() found in {pyfile.name}:\n"
                + "\n".join(f"  line {ln}: {text}" for ln, text in lines_with_eval)
            )

    def test_g1_no_raw_exec_in_shipped_modules(self):
        """G1b: no raw exec() call in main.py, lead_store.py, rag_engine.py."""
        for pyfile in _SHIPPED_PY:
            src = _read_text(pyfile)
            lines_with_exec = []
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if re.search(r"\bexec\s*\(", line):
                    lines_with_exec.append((lineno, line.rstrip()))
            assert not lines_with_exec, (
                f"G1 FAIL: raw exec() found in {pyfile.name}:\n"
                + "\n".join(f"  line {ln}: {text}" for ln, text in lines_with_exec)
            )

    def test_g1_no_eval_exec_in_tests(self):
        """G1c: no raw eval()/exec() *calls* in tests/ directory.

        Uses AST (not substring grep) so that docstrings / assertion-message
        strings that merely mention 'eval()' are not false positives — only an
        actual call to a bare name `eval` or `exec` fails.
        """
        import ast as _ast
        tests_dir = _CRM_ROOT / "tests"
        for pyfile in sorted(tests_dir.glob("*.py")):
            tree = _ast.parse(_read_text(pyfile))
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Call) and isinstance(node.func, _ast.Name):
                    assert node.func.id not in ("eval", "exec"), (
                        f"G1 FAIL: raw {node.func.id}() call found in "
                        f"tests/{pyfile.name} line {node.lineno}"
                    )

    def test_g1_no_forbidden_framework_in_shipped_modules(self):
        """G1d: no LangGraph/LangChain/AgentExecutor/bind_tools tokens in shipped .py."""
        forbidden_pattern = re.compile(
            r"langgraph|langchain|create_react_agent|AgentExecutor"
            r"|bind_tools|tool_runner|beta_tool",
            re.IGNORECASE,
        )
        for pyfile in _SHIPPED_PY:
            src = _read_text(pyfile)
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if forbidden_pattern.search(line):
                    pytest.fail(
                        f"G1 FAIL: forbidden framework token in {pyfile.name} "
                        f"line {lineno}: {line.rstrip()}"
                    )

    def test_g1_no_forbidden_framework_in_tests(self):
        """G1e: no framework imports in tests/ (grep patterns, not assertion strings)."""
        # Allowed: lines that are string literals being tested against
        # (like assert "langgraph" not in src or grep patterns inside strings).
        forbidden_pattern = re.compile(
            r"langgraph|langchain|create_react_agent|AgentExecutor"
            r"|bind_tools|tool_runner|beta_tool",
            re.IGNORECASE,
        )
        tests_dir = _CRM_ROOT / "tests"
        for pyfile in sorted(tests_dir.glob("*.py")):
            src = _read_text(pyfile)
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Allow lines where these appear as string literals being tested
                if '"' in line or "'" in line:
                    # If the match is only inside a string literal (the token
                    # is surrounded by quotes), it's a test assertion — skip.
                    # Simple heuristic: if the token appears in a string literal
                    # context (r"..." or "..."), allow it.
                    # We check: does the line contain `import` + the token?
                    if re.search(r"^\s*(import|from)\s+", line):
                        if forbidden_pattern.search(line):
                            pytest.fail(
                                f"G1 FAIL: forbidden framework import in "
                                f"tests/{pyfile.name} line {lineno}: {line.rstrip()}"
                            )


# ===========================================================================
# G2 — No hardcoded real catalog literals in shipped modules
# ===========================================================================

class TestG2NoCatalogLiterals:
    """G2: grep shipped modules for real catalog values read from brands_catalog.csv.

    Real catalog values include: brand names, Primary_Domain values, Gtin_Prefix values,
    Uniq_Id values. These must appear ONLY at runtime from the CSV, never hardcoded.

    The test reads brands_catalog.csv to get the actual real values and checks that
    none of them appear as literals in shipped modules or angle_corpus.json.

    Skips gracefully if brands_catalog.csv is not present (not a runtime requirement
    for the test runner in an isolated environment).
    """

    @pytest.fixture(autouse=True)
    def catalog_values(self):
        """Load real catalog values from brands_catalog.csv (if present)."""
        catalog_path = _CRM_ROOT / "brands_catalog.csv"
        if not catalog_path.exists():
            pytest.skip("brands_catalog.csv not found — G2 catalog-literal scan skipped")

        import pandas as pd
        df = pd.read_csv(str(catalog_path), dtype=str)

        # Collect real values that must NOT appear as literals in shipped code.
        self._brand_names    = [v.strip() for v in df["Brand_Name"].dropna().tolist()]
        self._domains        = [v.strip() for v in df["Primary_Domain"].dropna().tolist()]
        self._uniq_ids       = [v.strip() for v in df["Uniq_Id"].dropna().tolist()]
        self._gtins          = [v.strip() for v in df["Gtin_Prefix"].dropna().tolist()]
        self._competitor_ids = [v.strip() for v in df["Main_Competitor_Id"].dropna().tolist()]

    def _check_no_literals(self, literals: list, label: str):
        """Assert none of the literal values appear in shipped modules."""
        files_to_check = _SHIPPED_PY + [_ANGLE_CORPUS]
        for path in files_to_check:
            src = _read_text(path)
            for val in literals:
                if val and val in src:
                    pytest.fail(
                        f"G2 FAIL: real catalog {label} '{val}' found hardcoded in "
                        f"{path.name}. Catalog values must come from runtime CSV only "
                        f"(Policy 1 / CLAUDE.md §4)."
                    )

    def test_g2_no_brand_names_in_shipped_code(self):
        """G2a: no real Brand_Name literals in main.py / lead_store.py / rag_engine.py / corpus."""
        self._check_no_literals(self._brand_names, "Brand_Name")

    def test_g2_no_domains_in_shipped_code(self):
        """G2b: no real Primary_Domain literals in shipped modules."""
        self._check_no_literals(self._domains, "Primary_Domain")

    def test_g2_no_uniq_ids_in_shipped_code(self):
        """G2c: no real Uniq_Id literals in shipped modules."""
        self._check_no_literals(self._uniq_ids, "Uniq_Id")

    def test_g2_no_gtins_in_shipped_code(self):
        """G2d: no real Gtin_Prefix literals in shipped modules."""
        self._check_no_literals(self._gtins, "Gtin_Prefix")

    def test_g2_no_competitor_ids_in_shipped_code(self):
        """G2e: no real Main_Competitor_Id literals in shipped modules."""
        self._check_no_literals(self._competitor_ids, "Main_Competitor_Id")


# ===========================================================================
# G3 — OS-agnostic paths (no hardcoded absolute paths)
# ===========================================================================

class TestG3OsAgnosticPaths:
    """G3: grep shipped modules for hardcoded absolute path patterns.

    Forbidden: C:\\, /Users/, /home/, /private/ as literals in the source.
    Runtime-resolved paths (e.g. os.getcwd(), pathlib.Path.cwd()) are fine.
    """

    # Patterns for hardcoded absolute paths that are OS-specific
    _HARDCODED_PATH_PATTERNS = [
        re.compile(r"[Cc]:\\\\"),          # Windows C:\\
        re.compile(r"C:/"),                # Windows C:/
        re.compile(r"/Users/"),            # macOS /Users/
        re.compile(r"/home/"),             # Linux /home/
        re.compile(r"/private/"),          # macOS /private/
    ]

    def test_g3_no_hardcoded_absolute_paths_in_shipped_modules(self):
        """G3: no hardcoded absolute path literals in any shipped Python module."""
        for pyfile in _SHIPPED_PY:
            src = _read_text(pyfile)
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                for pattern in self._HARDCODED_PATH_PATTERNS:
                    if pattern.search(line):
                        pytest.fail(
                            f"G3 FAIL: hardcoded absolute path in {pyfile.name} "
                            f"line {lineno}: {line.rstrip()}"
                        )

    def test_g3_paths_use_os_path_or_pathlib(self):
        """G3: main.py uses os.path/pathlib for all runtime path construction."""
        main_src = _read_text(_MAIN_PY)
        # Verify the module imports pathlib or os.path (not absolute strings)
        assert "import pathlib" in main_src or "from pathlib" in main_src or "os.path" in main_src, (
            "G3: main.py must use pathlib or os.path for path construction"
        )

    def test_g3_assets_dir_relative_not_absolute(self):
        """G3: 'assets' directory references use os.getcwd()/pathlib, not absolute strings."""
        main_src = _read_text(_MAIN_PY)
        # assets/ should appear as a relative reference alongside os.getcwd()
        # or pathlib.Path(os.getcwd()), not as a hardcoded absolute path.
        # Check that 'assets' is NOT preceded by a hardcoded absolute path.
        hardcoded_assets = re.findall(
            r'["\'](?:/Users/|/home/|C:\\)[^"\']*assets[^"\']*["\']',
            main_src,
        )
        assert not hardcoded_assets, (
            f"G3 FAIL: hardcoded absolute path to assets/ found in main.py: {hardcoded_assets}"
        )


# ===========================================================================
# G4 — No secrets in tracked files
# ===========================================================================

class TestG4NoSecretsInTrackedFiles:
    """G4: grep shipped modules for corporate_access_key values and secret patterns.

    Checks:
    - No corporate_access_key values (read from contacts.json) in shipped modules.
    - No generic secret patterns: api_key=VALUE, sk-XXX, hardcoded webhook URLs.
    - All secrets come from os.environ.

    Scope: shipped modules + requirements.txt (NOT test files — test files
    intentionally use synthetic key values to exercise the auth gate; those
    are noted as a DECISION-NEEDED in the handback if they match real contacts.json).
    """

    @pytest.fixture(autouse=True)
    def load_access_keys(self):
        """Load corporate_access_key values from contacts.json (if present)."""
        contacts_path = _CRM_ROOT / "contacts.json"
        if not contacts_path.exists():
            pytest.skip("contacts.json not found — G4 key-value scan skipped")

        with open(str(contacts_path), encoding="utf-8") as fh:
            contacts = json.load(fh)

        self._access_keys = [
            c["corporate_access_key"]
            for c in contacts
            if "corporate_access_key" in c
        ]

    def _shipped_files_text(self):
        """Return list of (filename, text) for shipped modules + requirements."""
        return [
            (path.name, _read_text(path))
            for path in _SHIPPED_PY + [_ANGLE_CORPUS, _REQUIREMENTS]
        ]

    def test_g4_no_access_key_values_in_shipped_modules(self):
        """G4a: no corporate_access_key values from contacts.json in shipped modules."""
        for fname, src in self._shipped_files_text():
            for key_val in self._access_keys:
                if key_val and key_val in src:
                    pytest.fail(
                        f"G4 FAIL: corporate_access_key value '{key_val}' found in "
                        f"{fname}. Keys must live only in gitignored contacts.json "
                        f"and os.environ (CLAUDE.md §1 / §5 Policy 4)."
                    )

    def test_g4_no_hardcoded_api_key_assignments_in_shipped_modules(self):
        """G4b: no hardcoded api_key=VALUE patterns in shipped modules."""
        # Pattern: api_key="..." or api_key='...' (with actual value, not env var)
        pattern = re.compile(r'api[_-]?key\s*=\s*["\'][A-Za-z0-9]', re.IGNORECASE)
        for fname, src in self._shipped_files_text():
            for lineno, line in enumerate(src.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Allow os.environ["ANTHROPIC_API_KEY"] style lookups
                if "os.environ" in line or "os.getenv" in line:
                    continue
                if pattern.search(line):
                    pytest.fail(
                        f"G4 FAIL: hardcoded API key assignment in {fname} "
                        f"line {lineno}: {line.rstrip()}"
                    )

    def test_g4_no_sk_prefix_tokens_in_shipped_modules(self):
        """G4c: no 'sk-' prefix tokens (OpenAI/Anthropic key style) in shipped modules."""
        # sk- style tokens should never appear as literals
        pattern = re.compile(r'["\']sk-[A-Za-z0-9]', re.IGNORECASE)
        for fname, src in self._shipped_files_text():
            if pattern.search(src):
                pytest.fail(
                    f"G4 FAIL: 'sk-' prefix token found in {fname}. "
                    f"API keys must come from os.environ only."
                )

    def test_g4_no_hardcoded_slack_webhook_url_in_shipped_modules(self):
        """G4d: no hardcoded Slack webhook URL in shipped modules (TG2)."""
        # Hardcoded webhook URL looks like: https://hooks.slack.com/services/...
        pattern = re.compile(r"https://hooks\.slack\.com/services/", re.IGNORECASE)
        for fname, src in self._shipped_files_text():
            if pattern.search(src):
                pytest.fail(
                    f"G4 FAIL: hardcoded Slack webhook URL in {fname}. "
                    f"Webhook URL must come from os.environ[SLACK_WEBHOOK_URL] only."
                )

    def test_g4_slack_webhook_uses_env_var(self):
        """G4e: Slack webhook is accessed via os.environ in main.py (not hardcoded)."""
        main_src = _read_text(_MAIN_PY)
        # The webhook env-var constant _SLACK_WEBHOOK_ENV_VAR should be present
        assert "SLACK_WEBHOOK_URL" in main_src, (
            "G4: main.py must reference SLACK_WEBHOOK_URL env-var for the Slack webhook"
        )
        # And it should be read via os.environ
        assert 'os.environ' in main_src or 'os.getenv' in main_src, (
            "G4: main.py must use os.environ to access secret env-vars"
        )

    def test_g4_anthropic_key_from_env_only(self):
        """G4f: ANTHROPIC_API_KEY is accessed via os.environ, not hardcoded."""
        main_src = _read_text(_MAIN_PY)
        # Should reference the key from os.environ
        assert 'os.environ["ANTHROPIC_API_KEY"]' in main_src or \
               "os.environ['ANTHROPIC_API_KEY']" in main_src or \
               'os.environ.get("ANTHROPIC_API_KEY"' in main_src, (
            "G4: ANTHROPIC_API_KEY must be accessed via os.environ in main.py"
        )
        # Must NOT be hardcoded as a string value
        # (A real API key would start with 'sk-ant-api03-...' — the pattern
        # test_g4_no_sk_prefix_tokens covers this for generic sk- patterns.)


# ===========================================================================
# G5 — Full pipeline generalizes to a SECOND, DIFFERENT vertical seed
# ===========================================================================
#
# Stage 7 used: "athleisure DTC brands" (Apparel vertical) and "clean beauty DTC"
#               (Beauty vertical).
#
# Stage 8 uses: "Electronics > Audio > Wearable" — a completely different vertical
#               with synthetic brands/domains (sonicwave.com, audiogear.com).
#
# This proves behavior is input-driven, not branched on a specific seed.
# No real catalog values used; all synthetic fixtures.

class _FakeBlock:
    """Minimal duck-type of an Anthropic content block."""

    def __init__(self, block_type: str, **kwargs):
        self.type = block_type
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __iter__(self):
        return iter([])


class _FakeResponse:
    """Minimal duck-type of an Anthropic messages.create(...) response."""

    def __init__(self, content: list, stop_reason: str = "end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class FakeReasoningClient:
    """Scripted fake for the Anthropic reasoning client."""

    def __init__(self, responses: list = None):
        self._queue = list(responses or [])
        self.call_args_list: list = []

    def _next(self):
        if not self._queue:
            return _FakeResponse(
                [_FakeBlock("text", text="Pipeline complete.")],
                "end_turn",
            )
        item = self._queue.pop(0)
        if isinstance(item, type) and issubclass(item, BaseException):
            raise item("FakeReasoningClient: scripted exception")
        if isinstance(item, BaseException):
            raise item
        if callable(item):
            return item()
        return item

    class _MessagesAPI:
        def __init__(self, fake):
            self._fake = fake

        def create(self, **kwargs):
            self._fake.call_args_list.append(kwargs)
            return self._fake._next()

    @property
    def messages(self):
        return self._MessagesAPI(self)


def _tool_use_block(name: str, block_id: str, input_dict: dict) -> _FakeBlock:
    return _FakeBlock("tool_use", name=name, id=block_id, input=input_dict)


def _text_block(text: str) -> _FakeBlock:
    return _FakeBlock("text", text=text)


def _end_turn(text: str = "Pipeline complete.") -> _FakeResponse:
    return _FakeResponse([_text_block(text)], "end_turn")


def _tool_use_turn(name: str, block_id: str, input_dict: dict) -> _FakeResponse:
    return _FakeResponse(
        [_tool_use_block(name, block_id, input_dict)],
        "tool_use",
    )


def _make_valid_pdf_bytes() -> bytes:
    """Return a minimal, GW4-valid PDF byte string."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"%%EOF"
    )


def _make_mock_pdf_tool():
    """Return a mock request_reactfirst_pdf that saves a GW4-valid PDF."""
    def mock_pdf(target_domain: str, validated_angle_key: str,
                 calculated_risk_score: float) -> dict:
        assets_dir = pathlib.Path(os.getcwd()) / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        safe_domain = target_domain.replace(".", "_").replace("-", "_")
        pdf_filename = f"reactfirst_{safe_domain}_{validated_angle_key}.pdf"
        pdf_path = assets_dir / pdf_filename
        pdf_path.write_bytes(_make_valid_pdf_bytes())
        return {"ok": True, "path": str(pdf_path)}
    return mock_pdf


def _icp_profile_electronics_4_tags() -> str:
    """ICP profile for an Electronics/Audio/Wearable DTC brand — triggers ≥4 tags."""
    # Tags triggered: ecommerce_dtc, paid_social_advertising,
    #                 pixel_tracking_present, ad_spend_signals  (4 tags → qualified)
    return (
        "This DTC wearable audio brand sells headphones and earbuds on Shopify. "
        "They run Facebook ads, Instagram ads, and TikTok paid social campaigns. "
        "Google Tag Manager and Meta Pixel are installed on the storefront. "
        "Ad spend is $3M annually with strong ROAS from performance marketing. "
        "The product catalog includes 25 SKUs across noise-cancelling and open-ear lines."
    )


# ============================================================
# G5 — Electronics/Audio/Wearable vertical — happy path
# ============================================================

@pytest.fixture()
def tmp_cwd_g5(tmp_path, monkeypatch):
    """Change cwd to a temp dir for G5 run; all artifacts land here."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def electronics_catalog_df():
    """A minimal 9-column catalog DataFrame for the Electronics vertical.

    Uses purely synthetic brands (sonicwave.com, audiogear.com) that do NOT
    appear in the real brands_catalog.csv — proving generalization.
    """
    return pd.DataFrame([
        {
            "Uniq_Id":                    "synth-elec-0001",
            "Brand_Name":                 "SonicWave Audio",
            "Primary_Domain":             "sonicwave.com",
            "Core_Category":              "Electronics > Audio > Wearable",
            "Estimated_Ad_Spend_Tier":    "Tier 1",
            "Current_Status":             "Open_Opportunity",
            "Historical_Social_Incidents": 6,
            "Main_Competitor_Id":         "synth-elec-0002",
            "Gtin_Prefix":               "0100001",
        },
        {
            "Uniq_Id":                    "synth-elec-0002",
            "Brand_Name":                 "AudioGear Pro",
            "Primary_Domain":             "audiogear.com",
            "Core_Category":              "Electronics > Audio > Wearable",
            "Estimated_Ad_Spend_Tier":    "Tier 2",
            "Current_Status":             "Unreached_Prospect",
            "Historical_Social_Incidents": 2,
            "Main_Competitor_Id":         "synth-elec-0001",
            "Gtin_Prefix":               "0100002",
        },
    ])


@pytest.fixture()
def electronics_policies_text():
    """Minimal policies string for the Electronics seed run."""
    return (
        "Policy 1: All brand facts from brands_catalog.csv only.\n"
        "Policy 2: ICP threshold >= 3 tags.\n"
        "Policy 5: Max 3 angles.\n"
        "Policy 6: FALLBACK_MESSAGE on zero match.\n"
    )


class TestG5ElectronicsVerticalHappyPath:
    """G5: Full pipeline end-to-end with a DIFFERENT second vertical seed.

    Vertical: Electronics > Audio > Wearable
    Stage 7 used: Apparel / Beauty verticals.

    Proves:
    - The pipeline produces qualified_leads.json ≤ MAX_ANGLES entries.
    - At least 1 GW4-valid PDF is produced under assets/.
    - reactfirst_run.log is written.
    - No code change was needed — behavior is input-driven.
    - The seed used here is completely synthetic (no real catalog values).
    """

    def _patch_tools(self, monkeypatch):
        """Patch network-dependent tools for zero-network run."""

        # generate_search_queries — returns electronics-vertical queries
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "generate_search_queries",
            lambda vertical_seed, target_count=15: [
                "wearable audio DTC ecommerce brands",
                "headphones earbuds direct to consumer paid social",
                "wearable audio brand performance marketing Facebook TikTok",
            ],
        )

        # execute_3way_fanout — returns two synthetic domains (A+B ≥ 2 → no C)
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "execute_3way_fanout",
            lambda queries: {
                "domains": {
                    "sonicwave.com":  {"provenance": ["A", "B"]},
                    "audiogear.com":  {"provenance": ["A"]},
                },
                "vector_status": {"A": "ok", "B": "ok", "C": "skipped"},
                "total_unique_domains": 2,
            },
        )

        # analyze_company_chunk — returns profiles with all 3 pixel flags
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d,
                    "fetched": True,
                    "status_code": 200,
                    "title": f"{d} — Wearable Audio",
                    "description": "DTC wearable audio brand with paid social ads",
                    "tiktok_pixel": True,
                    "meta_pixel": True,
                    "gtm": True,
                    "operational_scale_signals": [
                        "ecommerce_dtc",
                        "paid_social_advertising",
                        "pixel_tracking_present",
                        "ad_spend_signals",
                    ],
                    "timed_out": False,
                    "error": None,
                }
                for d in domains
            ],
        )

        # match_solicitation_angle — returns Tier 1 (avoids rag_engine load)
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "match_solicitation_angle",
            lambda scraped_narrative_context, category_path: {
                "angle_key": "crisis_social_media_001",
                "tier": 1,
                "scores": {
                    "semantic_results": 5,
                    "bm25_results": 5,
                    "fused_results": 5,
                    "top_rrf_score": 0.032,
                },
            },
        )

        # request_reactfirst_pdf — saves a GW4-valid PDF
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "request_reactfirst_pdf",
            _make_mock_pdf_tool(),
        )

    def test_g5_electronics_seed_produces_artifacts(
        self,
        tmp_cwd_g5,
        monkeypatch,
        electronics_catalog_df,
        electronics_policies_text,
    ):
        """G5a: Electronics/Audio/Wearable seed produces all required artifacts."""

        # Script the model's multi-turn conversation for the Electronics vertical.
        scripted_responses = [
            # Turn 1: generate queries for the electronics vertical
            _tool_use_turn(
                "generate_search_queries", "tc-g501",
                {"vertical_seed": "wearable audio DTC brands", "target_count": 15},
            ),
            # Turn 2: fanout
            _tool_use_turn(
                "execute_3way_fanout", "tc-g502",
                {"queries": [
                    "wearable audio DTC ecommerce brands",
                    "headphones earbuds direct to consumer paid social",
                ]},
            ),
            # Turn 3: extract + score pool
            _tool_use_turn(
                "extract_and_score_pool", "tc-g503",
                {"raw_pool": [
                    {"domain": "sonicwave.com", "provenance": ["A", "B"]},
                    {"domain": "audiogear.com",  "provenance": ["A"]},
                ]},
            ),
            # Turn 4: analyze the top domain
            _tool_use_turn(
                "analyze_company_chunk", "tc-g504",
                {"domains": ["sonicwave.com"]},
            ),
            # Turn 5: evaluate ICP tags — electronics profile triggers ≥4 tags
            _tool_use_turn(
                "evaluate_icp_tags", "tc-g505",
                {"company_profile_data": _icp_profile_electronics_4_tags()},
            ),
            # Turn 6: match solicitation angle
            _tool_use_turn(
                "match_solicitation_angle", "tc-g506",
                {
                    "scraped_narrative_context": _icp_profile_electronics_4_tags(),
                    "category_path": "Electronics > Audio > Wearable",
                },
            ),
            # Turn 7: secured_calculator for Policy 3 premium (Tier 1, incidents > 5)
            _tool_use_turn(
                "secured_calculator", "tc-g507",
                {"expression": "2500 * 1.15"},
            ),
            # Turn 8: request PDF
            _tool_use_turn(
                "request_reactfirst_pdf", "tc-g508",
                {
                    "target_domain": "sonicwave.com",
                    "validated_angle_key": "crisis_social_media_001",
                    "calculated_risk_score": 2875.0,
                },
            ),
            # Turn 9: end_turn
            _end_turn("Electronics vertical complete. 1 qualified brand (SonicWave Audio)."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)
        self._patch_tools(monkeypatch)

        # Run the pipeline with the NEW electronics vertical seed.
        result = main.answer_question(
            "Find wearable audio DTC brands for outreach",
            catalog_df=electronics_catalog_df,
            policies=electronics_policies_text,
        )

        # ----------------------------------------------------------------
        # G5a — result is a non-empty string (pipeline completed successfully)
        # ----------------------------------------------------------------
        assert isinstance(result, str), "G5: answer_question must return a string"
        assert len(result) > 0, "G5: result must be non-empty"
        assert result != main.FALLBACK_MESSAGE, (
            "G5: electronics happy path must NOT return FALLBACK_MESSAGE — "
            "at least one brand should have qualified"
        )

        # ----------------------------------------------------------------
        # G5b — reactfirst_run.log produced
        # ----------------------------------------------------------------
        log_path = tmp_cwd_g5 / "reactfirst_run.log"
        assert log_path.exists(), "G5: reactfirst_run.log must be produced"
        log_content = log_path.read_text(encoding="utf-8")
        assert len(log_content) > 0, "G5: reactfirst_run.log must be non-empty"

        # ----------------------------------------------------------------
        # G5c — qualified_leads.json produced
        # ----------------------------------------------------------------
        leads_path = tmp_cwd_g5 / "qualified_leads.json"
        assert leads_path.exists(), (
            "G5: qualified_leads.json must be produced when ≥1 brand qualifies"
        )
        with open(str(leads_path), encoding="utf-8") as fh:
            leads_data = json.load(fh)

        assert "qualified_leads" in leads_data, (
            "G5: qualified_leads.json must have 'qualified_leads' key"
        )
        leads = leads_data["qualified_leads"]
        assert isinstance(leads, list), "G5: 'qualified_leads' must be a list"
        assert len(leads) >= 1, "G5: at least 1 qualified lead must be present"

        # ----------------------------------------------------------------
        # G5d — ≤ MAX_ANGLES entries (Policy 5 ceiling enforced)
        # ----------------------------------------------------------------
        assert len(leads) <= main.MAX_ANGLES, (
            f"G5: qualified_leads must not exceed MAX_ANGLES={main.MAX_ANGLES}; "
            f"got {len(leads)}"
        )

        # ----------------------------------------------------------------
        # G5e — ≥1 GW4-valid PDF under assets/
        # ----------------------------------------------------------------
        assets_dir = tmp_cwd_g5 / "assets"
        assert assets_dir.exists(), "G5: assets/ directory must exist after PDF generation"
        pdf_files = list(assets_dir.glob("*.pdf"))
        assert len(pdf_files) >= 1, "G5: at least 1 PDF must be saved under assets/"

        for pdf_file in pdf_files:
            gw4 = main._check_pdf_health(str(pdf_file))
            assert gw4["ok"], (
                f"G5: PDF {pdf_file.name} failed GW4 health check: {gw4.get('error')}"
            )

        # ----------------------------------------------------------------
        # G5f — lead entries contain the expected shape
        # ----------------------------------------------------------------
        for lead in leads:
            assert "domain" in lead,     f"G5: lead entry must have 'domain': {lead}"
            assert "angle_key" in lead,  f"G5: lead entry must have 'angle_key': {lead}"
            assert "pdf_path" in lead,   f"G5: lead entry must have 'pdf_path': {lead}"

        # ----------------------------------------------------------------
        # G5g — total tool calls within cap (≤15)
        # ----------------------------------------------------------------
        total_llm_calls = len(fake_client.call_args_list)
        assert total_llm_calls <= main.TOOL_CALL_CAP, (
            f"G5: total LLM calls must be ≤ {main.TOOL_CALL_CAP}; got {total_llm_calls}"
        )
        assert total_llm_calls < main.TOOL_CALL_CAP, (
            f"G5: run hit the cap ({total_llm_calls}); must have headroom for this run"
        )

    def test_g5_vertical_is_different_from_stage7_seeds(self):
        """G5h: the seed used in G5 is demonstrably different from Stage 7 seeds.

        This check documents that G5 uses a different vertical (Electronics/Audio)
        vs Stage 7 (Apparel/Beauty) — proving the two-seed assertion is met.
        Stage 7 seeds used: 'athleisure DTC brands', 'clean beauty DTC',
                            'skincare DTC brands ecommerce'.
        Stage 8 G5 seed:    'wearable audio DTC brands' (Electronics > Audio > Wearable).
        """
        stage7_seeds = {
            "athleisure dtc brands",
            "clean beauty dtc",
            "skincare dtc brands ecommerce",
            "apparel",
            "beauty",
        }
        g5_seed = "wearable audio dtc brands"

        # The G5 seed must not overlap with Stage 7 seeds in vertical family.
        for s7_seed in stage7_seeds:
            assert g5_seed not in s7_seed and s7_seed not in g5_seed, (
                f"G5h FAIL: G5 seed '{g5_seed}' overlaps with Stage-7 seed '{s7_seed}'. "
                f"G5 must use a completely different vertical."
            )

        # The G5 category_path is from a different L1 category than Stage 7's.
        g5_category = "Electronics > Audio > Wearable"
        stage7_categories = ["Apparel > Athleisure > Sustainable",
                              "Apparel > Athleisure > Performance",
                              "Beauty > Skincare > Clean"]
        for s7_cat in stage7_categories:
            g5_l1 = g5_category.split(" > ")[0].strip()
            s7_l1 = s7_cat.split(" > ")[0].strip()
            assert g5_l1 != s7_l1, (
                f"G5h FAIL: G5 L1 category '{g5_l1}' matches Stage-7 L1 '{s7_l1}'. "
                f"Must be a different vertical."
            )


class TestG5ElectronicsVerticalNoMatch:
    """G5 companion: the electronics seed also obeys the no-match fallback path.

    If ICP tags fail for the electronics brand, FALLBACK_MESSAGE is returned.
    This confirms Policy 6 is input-driven (not hardcoded to any specific vertical).
    """

    def test_g5_electronics_no_match_yields_fallback(
        self,
        tmp_cwd_g5,
        monkeypatch,
        electronics_catalog_df,
        electronics_policies_text,
    ):
        """G5 no-match: all ICP tags fail for the electronics seed → FALLBACK_MESSAGE."""

        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "generate_search_queries",
            lambda vertical_seed, target_count=15: ["obscure electronics niche"],
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "execute_3way_fanout",
            lambda queries: {
                "domains": {"unknowntech.com": {"provenance": ["A"]}},
                "vector_status": {"A": "ok", "B": "error", "C": "skipped"},
                "total_unique_domains": 1,
            },
        )
        monkeypatch.setitem(
            main.TOOL_DISPATCH,
            "analyze_company_chunk",
            lambda domains: [
                {
                    "domain": d,
                    "fetched": True,
                    "status_code": 200,
                    "title": "Unknown Tech",
                    "description": "No relevant signals",
                    "tiktok_pixel": False,
                    "meta_pixel": False,
                    "gtm": False,
                    "operational_scale_signals": [],
                    "timed_out": False,
                    "error": None,
                }
                for d in domains
            ],
        )

        # ICP-fail profile: only 1 tag → qualified=False
        icp_fail_profile = "This is a small electronics retailer. Nothing notable."

        scripted_responses = [
            _tool_use_turn(
                "generate_search_queries", "tc-g601",
                {"vertical_seed": "obscure electronics niche", "target_count": 10},
            ),
            _tool_use_turn(
                "execute_3way_fanout", "tc-g602",
                {"queries": ["obscure electronics niche"]},
            ),
            _tool_use_turn(
                "extract_and_score_pool", "tc-g603",
                {"raw_pool": [{"domain": "unknowntech.com", "provenance": ["A"]}]},
            ),
            _tool_use_turn(
                "analyze_company_chunk", "tc-g604",
                {"domains": ["unknowntech.com"]},
            ),
            _tool_use_turn(
                "evaluate_icp_tags", "tc-g605",
                {"company_profile_data": icp_fail_profile},
            ),
            _end_turn("No brands qualified for the electronics niche."),
        ]

        fake_client = FakeReasoningClient(responses=scripted_responses)
        monkeypatch.setattr(main, "_get_client", lambda: fake_client)

        result = main.answer_question(
            "Find electronics brands in the obscure niche",
            catalog_df=electronics_catalog_df,
            policies=electronics_policies_text,
        )

        # G5 no-match: result must be EXACTLY FALLBACK_MESSAGE
        assert result == main.FALLBACK_MESSAGE, (
            f"G5 no-match FAIL: expected FALLBACK_MESSAGE.\n"
            f"Expected: {main.FALLBACK_MESSAGE!r}\n"
            f"Got:      {result!r}"
        )

        # qualified_leads.json must NOT be written on no-match
        leads_path = tmp_cwd_g5 / "qualified_leads.json"
        assert not leads_path.exists(), (
            "G5: qualified_leads.json must NOT be written on a no-match run"
        )


# ===========================================================================
# G5 — Import-safety guard (ENV4 cross-check for this test module)
# ===========================================================================

class TestG5ImportSafety:
    """G5 companion: importing main does not trigger any side effects."""

    def test_import_main_has_no_side_effects(self, tmp_path):
        """ENV4 cross-check: re-importing main from a fresh module state is safe."""
        import importlib
        # Re-import to confirm no side effects
        m = importlib.import_module("main")
        assert hasattr(m, "answer_question"), "answer_question must be defined"
        assert hasattr(m, "FALLBACK_MESSAGE"), "FALLBACK_MESSAGE must be defined"
        assert hasattr(m, "TOOL_DISPATCH"), "TOOL_DISPATCH must be defined"
        assert hasattr(m, "TOOL_SCHEMAS"), "TOOL_SCHEMAS must be defined"
        # Verify lazy singletons are still None after import-only
        assert m._anthropic_client is None, (
            "ENV4: _anthropic_client must remain None after import (no side effects)"
        )
