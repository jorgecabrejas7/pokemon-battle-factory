import os
import sys
import logging

# Ensure scripts dir is in path to import other scripts
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import seeding functions
# Note: We assume these scripts have a main() or similar entry point we can call
try:
    from ingest_data import main as ingest_main
    from seed_facility_mons import seed_facility_mons
    # seed_items is largely redundant with ingest_data but we can run it if needed.
    # ingest_data does a better job with full item data.
except ImportError as e:
    print(f"Error importing seeding scripts: {e}")
    sys.exit(1)

def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Master Seeding Script.
    
    Orchestrates the entire database population process:
    1. Ingest Core Data (Species, Moves, Items) -> ingest_data.py
    2. Seed Facility Mons (Battle Factory Sets) -> seed_facility_mons.py
    """
    setup_logging()
    print("=== STARTING MASTER SEEDING PROCESS ===")
    
    print("\n[STEP 1/3] Ingesting Core Data (Species, Moves, Items)...")
    try:
        ingest_main()
    except Exception as e:
        print(f"Error in ingest_data: {e}")
        # sys.exit(1) # Optional: stop on error

    print("\n[STEP 2/3] Seeding All Item IDs...")
    try:
        # Import here to avoid early import issues if needed, or just rely on top-level
        from seed_items import parse_header, seed_db, HEADER_PATH
        items = parse_header(HEADER_PATH)
        seed_db(items)
    except Exception as e:
        print(f"Error in seed_items: {e}")

    print("\n[STEP 3/3] Seeding Battle Factory Pokémon Sets...")
    try:
        seed_facility_mons()
    except Exception as e:
        print(f"Error in seed_facility_mons: {e}")
        sys.exit(1)
        
    print("\n=== SEEDING COMPLETE ===")
    print("Run `python3 scripts/inspect_db.py` to verify the data.")

if __name__ == "__main__":
    main()
