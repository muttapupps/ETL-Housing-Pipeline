from pathlib import Path
import pandas as pd
import sqlite3

# Base directory so paths work inside Docker
BASE_DIR = Path(__file__).resolve().parent

# File paths
DB_PATH = BASE_DIR / "housing_final.db"

def drop_tables(conn):
    """
    Drop existing tables if they exist. Intended to be a fresh start for the database.
    """
    conn.execute("DROP TABLE IF EXISTS affordability_metrics")
    conn.execute("DROP TABLE IF EXISTS acs_income_info")
    conn.execute("DROP TABLE IF EXISTS hud_rent_info")
    conn.execute("DROP TABLE IF EXISTS zip_info")
    conn.execute("DROP TABLE IF EXISTS county_info")
    conn.execute("DROP TABLE IF EXISTS affordability_tiers")
    conn.execute("DROP TABLE IF EXISTS state_info")
    conn.commit()

    # Check if tables were dropped successfully by querying the sqlite_master table
    tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
    if not tables:
        return "All tables dropped successfully."
    else:
        return f"Remaining tables: {tables}"

def create_tables(conn):
    """
    Create the housing database tables with the appropriate schema. 
    The order of creation is important due to foreign key dependencies.
    """
    # First, the state_info table
    conn.execute("""
    CREATE TABLE state_info (
    state_fips VARCHAR(2) PRIMARY KEY,
    state_name TEXT
    )
    """)

    # Next, the affordability_tiers table
    conn.execute("DROP TABLE IF EXISTS affordability_tiers")
    conn.execute("""
    CREATE TABLE affordability_tiers (
    tier_id SERIAL PRIMARY KEY,
    tier_name TEXT,
    description TEXT
    )
    """)

    # Next, the county_info table which references state_info
    conn.execute("""
    CREATE TABLE county_info (
    fips VARCHAR(5) PRIMARY KEY,
    county_name TEXT,
    state_fips VARCHAR(2) REFERENCES state_info(state_fips)
    )
    """)

    # Next, the zip_info table which references county_info
    conn.execute("""
    CREATE TABLE zip_info (
    zip VARCHAR(5) PRIMARY KEY,
    city TEXT,
    metro TEXT,
    median_home_value NUMERIC,
    fips varchar(5) REFERENCES county_info(fips)
    )
    """)

    # Next, the hud_rent_info table which references county_info
    conn.execute("""
    CREATE TABLE hud_rent_info (
    hud_area_name TEXT,
    fips VARCHAR(5) REFERENCES county_info(fips),
    fmr_1br NUMERIC,
    fmr_2br NUMERIC,
    fmr_3br NUMERIC,
    PRIMARY KEY (hud_area_name, fips)
    )
    """)

    # Next, the acs_income_info table which references county_info
    conn.execute("""
    CREATE TABLE acs_income_info (
    fips VARCHAR(5) PRIMARY KEY,
    median_household_income NUMERIC,
    FOREIGN KEY (fips) REFERENCES county_info(fips)
    )
    """)

    # Finally, the afforability_metrics table which references county_info 
    # and affordability_tiers
    conn.execute("""
    CREATE TABLE affordability_metrics (
    zip VARCHAR(5) PRIMARY KEY REFERENCES zip_info(zip),
    price_to_income_ratio NUMERIC,
    rent_to_home_value_ratio NUMERIC,
    annual_rent_to_income_ratio NUMERIC,
    affordability_index NUMERIC,
    affordability_tier INTEGER REFERENCES affordability_tiers(tier_id)
    )
    """)

    conn.commit()
    # Verify tables were created successfully by querying the sqlite_master table
    tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
    expected_tables = {
        'state_info', 'affordability_tiers', 'county_info', 
        'zip_info', 'hud_rent_info', 'acs_income_info', 
        'affordability_metrics'
    }
    created_tables = set(t[0] for t in tables)
    if expected_tables.issubset(created_tables):
        table_list = "\n".join(created_tables)
        print(f"Tables created successfully:\n{table_list}")
        return "All tables created successfully."
    else:
        missing_tables = expected_tables - created_tables
        return f"Missing tables: {missing_tables}"


def main():
    # Connect to the SQLite database (it will be created if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)

    # Drop existing tables (if any) and create new ones
    print(drop_tables(conn))
    print(create_tables(conn))

    # Close the database connection
    conn.close()

if __name__ == "__main__":
    main()
