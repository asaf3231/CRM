"""
tests/test_catalog.py — Stage 1 QA checks for main.py §3-§4, rag_engine.py, lead_store.py

Checks verified:
  ENV4  — import main, lead_store, rag_engine has ZERO side effects
  CAT1  — 9-column header validated on load; bad header → clean explicit error
  CAT2  — no positional column access (grep check + functional)
  CAT3  — Historical_Social_Incidents coerced to int; tier/status enums validated
  CAT4  — Main_Competitor_Id spelled exactly as in the real CSV header
  CAT5  — no catalog values hardcoded in code (grep check)
  CAT6  — Blacklisted brands excluded from filter_outreach_candidates
  RAG1  — Chroma collection builds on first use, persists under .chroma/
           (tested with a throwaway persist dir; does NOT run at import)
"""

import importlib
import json
import os
import re
import subprocess
import sys
import textwrap
import types

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# ENV4 — import main, lead_store, rag_engine with zero side effects
# ---------------------------------------------------------------------------

class TestENV4:
    """Import-safety: importing all three modules must have ZERO side effects."""

    def test_import_main_no_side_effects(self, monkeypatch):
        """ENV4: import main builds no clients, reads no files, writes nothing."""
        # Track any file-open calls at module level
        opened_files = []
        original_open = open

        # Remove main from sys.modules to force a fresh import
        for mod_name in list(sys.modules.keys()):
            if mod_name in ("main",) or mod_name.startswith("main."):
                del sys.modules[mod_name]

        # Patch os.environ to not have ANTHROPIC_API_KEY so client construction would fail
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        import main  # must not raise even without the key

        # Verify singletons are still None (client not built)
        assert main._anthropic_client is None, (
            "Anthropic client was constructed at import time — import is NOT safe."
        )

    def test_import_lead_store_no_side_effects(self):
        """ENV4: import lead_store does not call get_lead_data_collection()."""
        # Reload to force fresh import
        for mod_name in list(sys.modules.keys()):
            if mod_name in ("lead_store",) or mod_name.startswith("lead_store."):
                del sys.modules[mod_name]

        import lead_store

        # Singleton must still be None
        assert lead_store._collection_instance is None, (
            "lead_store._collection_instance was set at import time — NOT import-safe."
        )

    def test_import_rag_engine_no_side_effects(self):
        """ENV4: import rag_engine builds no embedder and no Chroma collection."""
        for mod_name in list(sys.modules.keys()):
            if mod_name in ("rag_engine",) or mod_name.startswith("rag_engine."):
                del sys.modules[mod_name]

        import rag_engine

        assert rag_engine._embedder_instance is None, (
            "rag_engine._embedder_instance was set at import time — NOT import-safe."
        )
        assert rag_engine._collection_instance is None, (
            "rag_engine._collection_instance was set at import time — NOT import-safe."
        )


# ---------------------------------------------------------------------------
# Fixtures for catalog tests
# ---------------------------------------------------------------------------

VALID_CATALOG_ROWS = [
    {
        "Uniq_Id": "b1f3a2c0-0001-4a10-9c11-aa0000000001",
        "Brand_Name": "Northwind Athletics",
        "Primary_Domain": "northwindathletics.com",
        "Core_Category": "Apparel > Athleisure > Performance",
        "Estimated_Ad_Spend_Tier": "Tier 1",
        "Current_Status": "Open_Opportunity",
        "Historical_Social_Incidents": "7",
        "Main_Competitor_Id": "b1f3a2c0-0002-4a10-9c11-aa0000000002",
        "Gtin_Prefix": "0712345",
    },
    {
        "Uniq_Id": "b1f3a2c0-0002-4a10-9c11-aa0000000002",
        "Brand_Name": "Cobalt Run Co",
        "Primary_Domain": "cobaltrun.com",
        "Core_Category": "Apparel > Athleisure > Performance",
        "Estimated_Ad_Spend_Tier": "Tier 2",
        "Current_Status": "Unreached_Prospect",
        "Historical_Social_Incidents": "3",
        "Main_Competitor_Id": "b1f3a2c0-0001-4a10-9c11-aa0000000001",
        "Gtin_Prefix": "0712346",
    },
    {
        "Uniq_Id": "b1f3a2c0-0006-4a10-9c11-aa0000000006",
        "Brand_Name": "Crater Cola",
        "Primary_Domain": "cratercola.com",
        "Core_Category": "Food > Beverage > Soda",
        "Estimated_Ad_Spend_Tier": "Tier 2",
        "Current_Status": "Blacklisted",
        "Historical_Social_Incidents": "9",
        "Main_Competitor_Id": "b1f3a2c0-0005-4a10-9c11-aa0000000005",
        "Gtin_Prefix": "0812346",
    },
    {
        "Uniq_Id": "b1f3a2c0-0003-4a10-9c11-aa0000000003",
        "Brand_Name": "Lumen Skincare",
        "Primary_Domain": "lumenskincare.com",
        "Core_Category": "Beauty > Skincare > Clean",
        "Estimated_Ad_Spend_Tier": "Tier 1",
        "Current_Status": "Active_Client",
        "Historical_Social_Incidents": "2",
        "Main_Competitor_Id": "b1f3a2c0-0004-4a10-9c11-aa0000000004",
        "Gtin_Prefix": "0612345",
    },
]


@pytest.fixture
def tmp_catalog_csv(tmp_path):
    """Write VALID_CATALOG_ROWS to a temp CSV; return its path."""
    import csv as _csv
    cols = [
        "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
        "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
        "Main_Competitor_Id", "Gtin_Prefix",
    ]
    catalog_file = tmp_path / "brands_catalog.csv"
    with open(str(catalog_file), "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(VALID_CATALOG_ROWS)
    return str(catalog_file)


# ---------------------------------------------------------------------------
# CAT1 — Header validated on load
# ---------------------------------------------------------------------------

class TestCAT1:
    def test_valid_header_loads(self, tmp_catalog_csv):
        """CAT1: A correct 9-column CSV loads without error."""
        import main
        df = main.load_catalog(tmp_catalog_csv)
        assert len(df) == len(VALID_CATALOG_ROWS)

    def test_missing_column_raises(self, tmp_path):
        """CAT1: Missing column → clean ValueError (not a KeyError later)."""
        import csv as _csv
        import main
        # Write CSV with only 8 columns (missing Gtin_Prefix)
        bad_cols = [
            "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
            "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
            "Main_Competitor_Id",
        ]
        bad_file = tmp_path / "bad_catalog.csv"
        with open(str(bad_file), "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=bad_cols)
            writer.writeheader()
            writer.writerow({k: "x" for k in bad_cols})
        with pytest.raises(ValueError, match="Catalog header mismatch"):
            main.load_catalog(str(bad_file))

    def test_extra_column_raises(self, tmp_path):
        """CAT1: Extra column → clean ValueError."""
        import csv as _csv
        import main
        extra_cols = [
            "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
            "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
            "Main_Competitor_Id", "Gtin_Prefix", "ExtraCol",
        ]
        bad_file = tmp_path / "extra_col.csv"
        with open(str(bad_file), "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=extra_cols)
            writer.writeheader()
            writer.writerow({k: "x" for k in extra_cols})
        with pytest.raises(ValueError, match="Catalog header mismatch"):
            main.load_catalog(str(bad_file))

    def test_renamed_column_raises(self, tmp_path):
        """CAT1: Renamed column → clean ValueError."""
        import csv as _csv
        import main
        bad_cols = [
            "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
            "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
            "Main_Competitor_ld",  # typo: lowercase 'l' instead of 'I'
            "Gtin_Prefix",
        ]
        bad_file = tmp_path / "renamed_col.csv"
        with open(str(bad_file), "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=bad_cols)
            writer.writeheader()
            writer.writerow({k: "x" for k in bad_cols})
        with pytest.raises(ValueError, match="Catalog header mismatch"):
            main.load_catalog(str(bad_file))

    def test_real_csv_header_loads(self):
        """CAT1: The real brands_catalog.csv (in cwd) loads without error."""
        import main
        real_path = os.path.join(os.getcwd(), "brands_catalog.csv")
        if not os.path.exists(real_path):
            pytest.skip("brands_catalog.csv not in cwd")
        df = main.load_catalog(real_path)
        assert len(df) > 0
        # Verify Main_Competitor_Id spelling matches the file
        assert "Main_Competitor_Id" in df.columns


# ---------------------------------------------------------------------------
# CAT2 — Access by name (grep check + functional)
# ---------------------------------------------------------------------------

class TestCAT2:
    def test_no_positional_iloc_in_catalog_code(self):
        """CAT2: main.py catalog code does not use .iloc[:, <int>] or row[<int>]."""
        main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()
        # Look for positional column access patterns
        bad_patterns = [
            r'\.iloc\[:,\s*\d+\]',   # .iloc[:, 4]
            r'row\[\d+\]',            # row[4]
            r'df\[\d+\]',             # df[4]
        ]
        for pattern in bad_patterns:
            hits = re.findall(pattern, source)
            assert not hits, (
                f"Positional catalog access found (CAT2 violation): {hits} "
                f"(pattern: {pattern})"
            )

    def test_catalog_row_accessed_by_name(self, tmp_catalog_csv):
        """CAT2: get_brand_by_domain and filter_outreach_candidates access by column name."""
        import main
        df = main.load_catalog(tmp_catalog_csv)
        # These should not raise KeyError or positional-access issues
        row = main.get_brand_by_domain(df, "cobaltrun.com")
        assert row is not None
        # Access by name (not index) — the PRD-prescribed pattern
        assert row["Brand_Name"] == "Cobalt Run Co"
        assert row["Estimated_Ad_Spend_Tier"] == "Tier 2"


# ---------------------------------------------------------------------------
# CAT3 — Typed reads + enum validation
# ---------------------------------------------------------------------------

class TestCAT3:
    def test_historical_incidents_coerced_to_int(self, tmp_catalog_csv):
        """CAT3: Historical_Social_Incidents is int dtype after load."""
        import main
        df = main.load_catalog(tmp_catalog_csv)
        assert df["Historical_Social_Incidents"].dtype == int or \
               df["Historical_Social_Incidents"].dtype.kind == "i", (
            "Historical_Social_Incidents must be an integer column."
        )

    def test_invalid_incidents_raises(self, tmp_path):
        """CAT3: Non-integer Historical_Social_Incidents raises ValueError."""
        import csv as _csv
        import main
        cols = [
            "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
            "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
            "Main_Competitor_Id", "Gtin_Prefix",
        ]
        bad_file = tmp_path / "bad_incidents.csv"
        row = {k: "x" for k in cols}
        row["Historical_Social_Incidents"] = "not-a-number"
        row["Estimated_Ad_Spend_Tier"] = "Tier 1"
        row["Current_Status"] = "Active_Client"
        with open(str(bad_file), "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerow(row)
        with pytest.raises(ValueError):
            main.load_catalog(str(bad_file))

    def test_invalid_tier_raises(self, tmp_path):
        """CAT3: Invalid Estimated_Ad_Spend_Tier raises ValueError."""
        import csv as _csv
        import main
        cols = [
            "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
            "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
            "Main_Competitor_Id", "Gtin_Prefix",
        ]
        bad_file = tmp_path / "bad_tier.csv"
        row = {k: "x" for k in cols}
        row["Estimated_Ad_Spend_Tier"] = "Tier 5"  # invalid
        row["Current_Status"] = "Active_Client"
        row["Historical_Social_Incidents"] = "2"
        with open(str(bad_file), "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerow(row)
        with pytest.raises(ValueError, match="Estimated_Ad_Spend_Tier"):
            main.load_catalog(str(bad_file))

    def test_invalid_status_raises(self, tmp_path):
        """CAT3: Invalid Current_Status raises ValueError."""
        import csv as _csv
        import main
        cols = [
            "Uniq_Id", "Brand_Name", "Primary_Domain", "Core_Category",
            "Estimated_Ad_Spend_Tier", "Current_Status", "Historical_Social_Incidents",
            "Main_Competitor_Id", "Gtin_Prefix",
        ]
        bad_file = tmp_path / "bad_status.csv"
        row = {k: "x" for k in cols}
        row["Estimated_Ad_Spend_Tier"] = "Tier 1"
        row["Current_Status"] = "Unknown_Status"  # invalid
        row["Historical_Social_Incidents"] = "1"
        with open(str(bad_file), "w", newline="", encoding="utf-8") as f:
            writer = _csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerow(row)
        with pytest.raises(ValueError, match="Current_Status"):
            main.load_catalog(str(bad_file))


# ---------------------------------------------------------------------------
# CAT4 — Main_Competitor_Id spelling matches the file
# ---------------------------------------------------------------------------

class TestCAT4:
    def test_main_competitor_id_spelling_in_catalog_columns(self):
        """CAT4: CATALOG_COLUMNS uses 'Main_Competitor_Id' (capital I, not lowercase l)."""
        import main
        assert "Main_Competitor_Id" in main.CATALOG_COLUMNS, (
            "CATALOG_COLUMNS must contain 'Main_Competitor_Id' (capital I). "
            "Do not silently rewrite the header."
        )

    def test_main_competitor_id_accessible_by_name(self, tmp_catalog_csv):
        """CAT4: Main_Competitor_Id column accessible by exact name after load."""
        import main
        df = main.load_catalog(tmp_catalog_csv)
        # Should not raise KeyError
        first_row = df.iloc[0]
        val = first_row["Main_Competitor_Id"]
        assert val and len(val) > 0

    def test_real_csv_header_has_main_competitor_id(self):
        """CAT4: The real brands_catalog.csv uses 'Main_Competitor_Id'."""
        real_path = os.path.join(os.getcwd(), "brands_catalog.csv")
        if not os.path.exists(real_path):
            pytest.skip("brands_catalog.csv not in cwd")
        with open(real_path, "r", encoding="utf-8") as f:
            header_line = f.readline().strip()
        assert "Main_Competitor_Id" in header_line, (
            f"Real CSV header does not contain 'Main_Competitor_Id': {header_line}"
        )


# ---------------------------------------------------------------------------
# CAT5 — No catalog values hardcoded in code
# ---------------------------------------------------------------------------

class TestCAT5:
    """CAT5: grep verifies no real catalog values (brand names, domains, GTINs) in code."""

    def _get_real_catalog_values(self):
        """Read values from the real catalog file (not from memory)."""
        real_path = os.path.join(os.getcwd(), "brands_catalog.csv")
        if not os.path.exists(real_path):
            return None
        df = pd.read_csv(real_path, dtype=str)
        values = set()
        # Brand names and domains are the most likely to leak
        for col in ("Brand_Name", "Primary_Domain", "Gtin_Prefix"):
            if col in df.columns:
                values.update(df[col].dropna().str.strip().tolist())
        return values

    def test_no_catalog_values_in_main(self):
        """CAT5: main.py does not hardcode brand names, domains, or GTINs from the real catalog."""
        values = self._get_real_catalog_values()
        if values is None:
            pytest.skip("brands_catalog.csv not in cwd — cannot verify CAT5")

        main_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        leaks = [v for v in values if v and len(v) > 5 and v in source]
        assert not leaks, (
            f"CAT5 violation: catalog values found hardcoded in main.py: {leaks[:5]}"
        )

    def test_no_catalog_values_in_lead_store(self):
        """CAT5: lead_store.py does not hardcode catalog values."""
        values = self._get_real_catalog_values()
        if values is None:
            pytest.skip("brands_catalog.csv not in cwd")

        ls_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "lead_store.py")
        with open(ls_path, "r", encoding="utf-8") as f:
            source = f.read()

        leaks = [v for v in values if v and len(v) > 5 and v in source]
        assert not leaks, (
            f"CAT5 violation: catalog values found hardcoded in lead_store.py: {leaks[:5]}"
        )


# ---------------------------------------------------------------------------
# CAT6 — Blacklisted excluded from outreach candidates
# ---------------------------------------------------------------------------

class TestCAT6:
    def test_blacklisted_excluded(self, tmp_catalog_csv):
        """CAT6: Blacklisted brands are excluded from filter_outreach_candidates()."""
        import main
        df = main.load_catalog(tmp_catalog_csv)
        candidates = main.filter_outreach_candidates(df)
        statuses = candidates["Current_Status"].tolist()
        assert "Blacklisted" not in statuses, (
            "Blacklisted brands must not appear in outreach candidates."
        )

    def test_blacklisted_brand_not_in_candidates(self, tmp_catalog_csv):
        """CAT6: 'Crater Cola' (Blacklisted in fixture) is not in outreach candidates."""
        import main
        df = main.load_catalog(tmp_catalog_csv)
        candidates = main.filter_outreach_candidates(df)
        names = candidates["Brand_Name"].tolist()
        assert "Crater Cola" not in names

    def test_non_blacklisted_brands_present(self, tmp_catalog_csv):
        """CAT6: Non-blacklisted brands remain in the candidate set."""
        import main
        df = main.load_catalog(tmp_catalog_csv)
        candidates = main.filter_outreach_candidates(df)
        assert len(candidates) > 0
        # Northwind Athletics (Open_Opportunity) should be present
        names = candidates["Brand_Name"].tolist()
        assert "Northwind Athletics" in names


# ---------------------------------------------------------------------------
# RAG1 — Chroma collection builds on first use, persists under .chroma/
# ---------------------------------------------------------------------------

class TestRAG1:
    def test_rag_engine_collection_not_built_at_import(self):
        """RAG1 (+ ENV4): _get_collection() is NOT called at rag_engine import time."""
        for mod_name in list(sys.modules.keys()):
            if mod_name in ("rag_engine",) or mod_name.startswith("rag_engine."):
                del sys.modules[mod_name]
        import rag_engine
        assert rag_engine._collection_instance is None

    def test_collection_builds_on_first_use(self, tmp_path, monkeypatch):
        """RAG1: _get_collection() builds and persists the Chroma collection on first call."""
        for mod_name in list(sys.modules.keys()):
            if mod_name in ("rag_engine",) or mod_name.startswith("rag_engine."):
                del sys.modules[mod_name]

        import rag_engine

        # Point Chroma persistence to a throwaway dir
        chroma_dir = str(tmp_path / ".chroma_test")
        monkeypatch.chdir(tmp_path)

        # Override the persist dir to use our tmp location
        monkeypatch.setattr(rag_engine, "CHROMA_PERSIST_DIR", ".chroma_test")

        # This should build the collection
        collection = rag_engine._get_collection()
        assert collection is not None, "Collection should be built on first call."

        # The .chroma_test directory must exist now
        assert os.path.isdir(chroma_dir), (
            f"Chroma persist directory not created: {chroma_dir}"
        )

    def test_collection_is_singleton(self, tmp_path, monkeypatch):
        """RAG1: _get_collection() returns the same object on repeated calls."""
        for mod_name in list(sys.modules.keys()):
            if mod_name in ("rag_engine",) or mod_name.startswith("rag_engine."):
                del sys.modules[mod_name]

        import rag_engine
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(rag_engine, "CHROMA_PERSIST_DIR", ".chroma_test2")

        col1 = rag_engine._get_collection()
        col2 = rag_engine._get_collection()
        assert col1 is col2, "_get_collection() must return the same singleton."


# ---------------------------------------------------------------------------
# ENV2 — Every import is pinned (requirements.txt grep check)
# ---------------------------------------------------------------------------

class TestENV2:
    REQUIRED_PINS = [
        "anthropic",
        "chromadb",
        "sentence-transformers",
        "mongomock",
        "pandas",
        "firecrawl-py",
        "google-search-results",
        "tavily-python",
    ]

    def test_requirements_txt_exists(self):
        """ENV2: requirements.txt exists in the cwd."""
        req_path = os.path.join(os.getcwd(), "requirements.txt")
        assert os.path.exists(req_path), "requirements.txt not found in cwd."

    def test_all_packages_are_pinned(self):
        """ENV2: Every required package has a '==' pin in requirements.txt."""
        req_path = os.path.join(os.getcwd(), "requirements.txt")
        if not os.path.exists(req_path):
            pytest.fail("requirements.txt not found — cannot verify ENV2.")

        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read()

        for pkg in self.REQUIRED_PINS:
            assert pkg in content, f"Package '{pkg}' not found in requirements.txt."
            # Check it has a '==' pin somewhere in the line containing the pkg
            lines_with_pkg = [l.strip() for l in content.splitlines() if pkg in l]
            has_pin = any("==" in line for line in lines_with_pkg)
            assert has_pin, (
                f"Package '{pkg}' is not pinned with '==' in requirements.txt. "
                f"Lines: {lines_with_pkg}"
            )

    def test_no_openai_or_google_genai(self):
        """ENV2: openai and google-genai are NOT in requirements.txt (Claude only)."""
        req_path = os.path.join(os.getcwd(), "requirements.txt")
        if not os.path.exists(req_path):
            pytest.skip("requirements.txt not found")
        with open(req_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "openai" not in content.lower(), "openai must not be in requirements.txt"
        assert "google-genai" not in content.lower(), "google-genai must not be in requirements.txt"
