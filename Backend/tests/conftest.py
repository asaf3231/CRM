"""
tests/conftest.py — ReactFirst AI Proactive Outbound Engine
Shared pytest fixtures for the full test suite.

INTG2 — Singleton reset autouse fixture:
    Resets the lazy singletons to None BEFORE and AFTER every test so that
    any seed written during a server lifespan (Stage I2+) or by an earlier test
    does not leak into CRM*/DISC*/ENV4 tests.

    Singletons reset:
        db._client                       (shared Mongo client — DB5)
        crm_store._leads_collection      (mini-CRM lead workspace)
        lead_store._collection_instance  (CRM contacts store)
        api_seed._icp_collection         (ICP durable substrate — CONN9)
        pipeline_runner._jobs_collection (discovery job store — CONN7)

    The import of crm_store / lead_store / db happens inside the fixture so the
    fixture itself is import-safe at collection time.  A getattr/try guard
    makes it safe even if an attribute is absent in a future refactor.
"""

import pytest


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset lazy singleton stores before and after every test (INTG2 / DB5).

    Function-scoped (default) so it runs around each individual test.
    Guards with try/getattr so it is harmless if an attribute is absent.
    """
    # --- pre-test reset ---
    try:
        import db
        db._client = None
    except Exception:
        pass

    try:
        import crm_store
        crm_store._leads_collection = None
    except Exception:
        pass

    try:
        import lead_store
        lead_store._collection_instance = None
    except Exception:
        pass

    try:
        import api_seed
        api_seed._icp_collection = None
    except Exception:
        pass

    try:
        import pipeline_runner
        pipeline_runner._jobs_collection = None
    except Exception:
        pass

    yield  # run the test

    # --- post-test reset ---
    try:
        import db
        db._client = None
    except Exception:
        pass

    try:
        import crm_store
        crm_store._leads_collection = None
    except Exception:
        pass

    try:
        import lead_store
        lead_store._collection_instance = None
    except Exception:
        pass

    try:
        import api_seed
        api_seed._icp_collection = None
    except Exception:
        pass

    try:
        import pipeline_runner
        pipeline_runner._jobs_collection = None
    except Exception:
        pass
