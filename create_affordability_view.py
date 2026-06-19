from pathlib import Path
import pandas as pd
import sqlite3

# Base directory so paths work inside Docker
BASE_DIR = Path(__file__).resolve().parent

# File paths
DB_PATH = BASE_DIR / "housing_final.db"

def create_affordability_view(conn: sqlite3.Connection):
    """
    Create a view in the database that combines all relevant information for affordability metrics.
    This view will be used to simplify queries when retrieving metrics for the API.
    """
    create_view_query = '''
    CREATE VIEW IF NOT EXISTS zip_affordability_view AS
    SELECT
    am.zip,
    z.city,
    s.state_name,
    z.median_home_value,
    h.fmr_1br,
    h.fmr_2br,
    h.fmr_3br,
    a.median_household_income,
    am.affordability_index,
    at.description
    FROM affordability_metrics am
    JOIN zip_info z ON am.zip = z.zip
    JOIN county_info c ON z.fips = c.fips
    JOIN state_info s ON c.state_fips = s.state_fips
    JOIN hud_rent_info h ON c.fips = h.fips
    JOIN acs_income_info a ON z.fips = a.fips
    JOIN affordability_tiers at ON am.affordability_tier = at.tier_id
    '''
    # Delete the view if it already exists to ensure we have the most up-to-date data
    conn.execute("DROP VIEW IF EXISTS zip_affordability_view")
    conn.execute(create_view_query)
    conn.commit()
    
    # Check if the view was created successfully by querying the sqlite_master table
    views = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='view' AND name='zip_affordability_view';"
    ).fetchall()
    if views:
        print("Affordability metrics view created successfully.")
    else:
        print("Failed to create affordability metrics view.")

def main():
    # Connect to the database and create the view
    conn = sqlite3.connect(DB_PATH)
    create_affordability_view(conn)
    conn.close()

if __name__ == "__main__":
    main()