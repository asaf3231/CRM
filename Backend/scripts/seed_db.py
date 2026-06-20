"""
scripts/seed_db.py — ReactFirst AI Proactive Outbound Engine
Idempotent database seed script (DB8).

Usage:
    python scripts/seed_db.py

Loads contacts.json into the configured MongoDB and ensures the CRM leads
collection and its indexes exist.  Designed to be run from the project root
(cwd must contain contacts.json).

Idempotency contract:
    - Contacts are seeded ONLY when the collection is empty (seed-if-empty).
      Running this script twice against a live Mongo yields no duplicate contacts.
    - The CRM leads workspace starts empty and is populated by upserts — re-running
      this script does not modify existing lead records.

MONGO_URI gate:
    - If MONGO_URI is set: connects to real MongoDB and creates the unique indexes.
    - If MONGO_URI is unset: falls back to the in-memory mongomock client.
      A clear warning is printed so the caller knows data will NOT persist.

Import-safe: no work is done at import time; all logic is inside main().
"""

import os
import sys


def main() -> None:
    """Seed the database idempotently and print a short summary."""
    # Resolve the project root (one directory above scripts/).
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(scripts_dir)

    # Change cwd so the store loaders find contacts.json etc. in the project root.
    os.chdir(project_root)

    # Add project root to the import path so we can import the store modules.
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Check whether we're talking to a real Mongo or the in-memory fallback.
    mongo_uri_set = bool(os.environ.get("MONGO_URI"))
    if not mongo_uri_set:
        print(
            "[seed_db] WARNING: MONGO_URI is not set. Seeding into the ephemeral "
            "in-memory mongomock store — data will NOT persist across process restarts."
        )

    # Import the store getters AFTER cwd/sys.path are set up.
    import lead_store  # noqa: E402
    import crm_store   # noqa: E402

    # get_lead_data_collection() seeds contacts.json only when the collection is empty.
    contacts_col = lead_store.get_lead_data_collection()
    contact_count = contacts_col.count_documents({})

    # get_crm_collection() builds the leads workspace and creates the unique index
    # (real Mongo only, gated inside the getter).
    leads_col = crm_store.get_crm_collection()
    lead_count = leads_col.count_documents({})

    print(
        f"[seed_db] contacts: {contact_count}, "
        f"leads: {lead_count}, "
        f"MONGO_URI set? {'yes' if mongo_uri_set else 'no'}"
    )


if __name__ == "__main__":
    main()
