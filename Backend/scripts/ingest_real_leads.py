#!/usr/bin/env python3
"""
ingest_real_leads.py — one-off live ingest of real qualified leads into the CRM store.

Runs the REAL pipeline tools directly (no LLM 15-call loop) over the catalog brands:

    load_catalog → analyze_company_chunk (live Firecrawl crawl + pixel detection)
                 → ICP gate (>= ICP_TAG_THRESHOLD live signals)
                 → compute_win_prob (catalog tier/incidents + live icp/pixel counts)
                 → crm_store.upsert_lead  (durable, keyed on catalog Uniq_Id)

Everything is genuinely live-crawled and governance-clean (Policy 1: every brand fact
comes from brands_catalog.csv; qualification uses the real ICP_TAG_THRESHOLD constant).
Blacklisted brands are excluded; synthetic catalog rows whose domains don't resolve simply
fail the crawl and are skipped. Idempotent: re-running upserts the same uniq_ids in place.

Usage (writes to whatever MONGO_URI / DB_NAME point at; mongomock if unset):
    cd Backend
    set -a; . ./.env; set +a                 # FIRECRAWL_API_KEY (+ others)
    MONGO_URI="<atlas-uri>" DB_NAME=gtm_db ../.venv/bin/python scripts/ingest_real_leads.py
"""

import os
import sys

# Make Backend/ importable when run from scripts/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main          # noqa: E402
import crm_store     # noqa: E402


def main_ingest() -> int:
    cwd = os.getcwd()
    catalog_path = os.path.join(cwd, "brands_catalog.csv")
    if not os.path.exists(catalog_path):
        # fall back to the Backend/ dir next to this script
        catalog_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "brands_catalog.csv",
        )
    df = main.load_catalog(catalog_path)

    # Outreach-eligible catalog rows only (Blacklisted excluded — CAT6 / Policy).
    eligible = df[df["Current_Status"] != "Blacklisted"]
    domains = [str(d).strip().lower() for d in eligible["Primary_Domain"]]
    print(f"[ingest] crawling {len(domains)} eligible catalog domains (live Firecrawl)...")

    profiles = {p.get("domain"): p for p in main.analyze_company_chunk(domains)}

    persisted, skipped = [], []
    for _, row in eligible.iterrows():
        domain = str(row["Primary_Domain"]).strip().lower()
        prof = profiles.get(domain, {})
        signals = prof.get("operational_scale_signals", []) or []
        icp_count = len(signals)
        pixel_count = sum(
            1 for k in ("tiktok_pixel", "meta_pixel", "gtm") if prof.get(k)
        )

        if icp_count < main.ICP_TAG_THRESHOLD:
            skipped.append((row["Brand_Name"], domain, icp_count, prof.get("fetched")))
            continue

        tier = str(row["Estimated_Ad_Spend_Tier"]).strip()
        incidents = int(row["Historical_Social_Incidents"])
        win_prob = crm_store.compute_win_prob(tier, incidents, icp_count, pixel_count)

        record = {
            "uniq_id": str(row["Uniq_Id"]).strip(),
            "domain": domain,
            "company": str(row["Brand_Name"]).strip(),
            "status": "qualified",
            "stage": "in_crm",
            "win_prob": win_prob,
            "profile": {
                "icp_tags": signals,
                "title": prof.get("title", ""),
                "pixels": {
                    "tiktok_pixel": bool(prof.get("tiktok_pixel")),
                    "meta_pixel": bool(prof.get("meta_pixel")),
                    "gtm": bool(prof.get("gtm")),
                },
                "category_path": str(row["Core_Category"]).strip(),
            },
            "icp_count": icp_count,
            "historical_social_incidents": incidents,
            "current_status": str(row["Current_Status"]).strip(),
            "contact_ids": [],
        }
        import api_adapters  # real RAG-matched solicitation angle, persisted (C13)
        record["angle"] = api_adapters.real_angle_for_record(record)
        crm_store.upsert_lead(record)
        persisted.append((record["company"], domain, icp_count, round(win_prob, 2)))

    print(f"\n[ingest] PERSISTED {len(persisted)} qualified real leads:")
    for company, domain, n, wp in sorted(persisted, key=lambda x: -x[3]):
        print(f"    QUAL  {company:24s} {domain:20s} icp={n}  win_prob={wp}")
    print(f"\n[ingest] skipped {len(skipped)} (below ICP gate or uncrawlable):")
    for company, domain, n, fetched in skipped:
        print(f"    ----  {company:24s} {domain:20s} icp={n}  fetched={fetched}")

    total = crm_store.get_crm_collection().count_documents({})
    print(f"\n[ingest] crm_store leads total now: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_ingest())
