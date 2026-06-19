from pathlib import Path
import pandas as pd
import sqlite3
import requests

# Base directory so paths work inside Docker
BASE_DIR = Path(__file__).resolve().parent

# File paths
DB_PATH = BASE_DIR / "housing_final.db"
ZILLOW_PATH = BASE_DIR / "zillow_full_data.csv"   # change if needed
HUD_PATH = BASE_DIR / "hud_county_data.csv"

# Define API parameters for the acs dataset
# Parameterized API settings
BASE_URL = "https://api.census.gov/data"
YEAR = "2022"
DATASET = "acs/acs5"
VARIABLES = [
    "NAME",
    "B19013_001E",   # Median household income
]
GEOGRAPHY = "county:*"

output_acs_csv = BASE_DIR / f"acs_income_data_{YEAR}.csv"

# Define function to standardize county names
def normalize_county(series: pd.Series) -> pd.Series:
    """
    Standardize county names for joining.
    """
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )

def clean_hud_fips(series: pd.Series) -> pd.Series:
    """
    Fix HUD FIPS values that were exported with trailing 9s.

    Examples:
    100199999  -> 01001
    603799999  -> 06037
    4815799999 -> 48157
    """
    numeric_fips = pd.to_numeric(series, errors="coerce")
    cleaned = (numeric_fips // 100000).astype("Int64")
    return cleaned.astype(str).str.replace("<NA>", "", regex=False).str.zfill(5)

def load_and_clean_csvs() -> None:
    """
    Load the Zillow and HUD datasets, perform cleaning operations, and return 
    cleaned versions as DataFrames.
    """
   # Load in and clean csv data into temp dataframes
    # Load raw datasets
    zillow = pd.read_csv(ZILLOW_PATH)
    hud = pd.read_csv(HUD_PATH)

    # Standardize column names
    zillow.columns = [c.strip().lower() for c in zillow.columns]
    hud.columns = [c.strip().lower() for c in hud.columns]

    print("Zillow source columns:", zillow.columns.tolist()[:15], "...")
    print("HUD source columns:", hud.columns.tolist())

    # -----------------------------
    # Zillow cleanup
    # -----------------------------
    required_zillow_cols = ["regionname", "city", "state", "metro", "countyname"]
    missing_zillow = [c for c in required_zillow_cols if c not in zillow.columns]
    if missing_zillow:
        raise ValueError(f"Zillow file is missing expected columns: {missing_zillow}")

    # Find the most recent Zillow value column automatically
    date_cols = [c for c in zillow.columns if c[:4].isdigit() and "-" in c]
    if not date_cols:
        raise ValueError("No Zillow date columns found.")

    latest_col = sorted(date_cols)[-1]
    print(f"Using Zillow latest value column: {latest_col}")

    zillow_clean = zillow[["regionname", "city", "state", "metro", "countyname", latest_col]].copy()
    zillow_clean = zillow_clean.rename(
        columns={
            "regionname": "zip",
            "countyname": "county",
            latest_col: "median_home_value",
            }
        )

    zillow_clean["state"] = zillow_clean["state"].astype(str).str.strip().str.lower()
    zillow_clean["county"] = normalize_county(zillow_clean["county"])
    zillow_clean["city"] = zillow_clean["city"].astype(str).str.strip()
    zillow_clean["metro"] = zillow_clean["metro"].astype(str).str.strip()
    zillow_clean["zip"] = zillow_clean["zip"].astype(str).str.strip()
    zillow_clean["median_home_value"] = pd.to_numeric(
        zillow_clean["median_home_value"], errors="coerce"
        )

    # -----------------------------
    # HUD cleanup
    # -----------------------------
    required_hud_cols = ["stusps", "countyname", "hud_area_name", "fips", "fmr_1", "fmr_2", "fmr_3"]
    missing_hud = [c for c in required_hud_cols if c not in hud.columns]
    if missing_hud:
        raise ValueError(f"HUD file is missing expected columns: {missing_hud}")

    hud_clean = hud[required_hud_cols].copy()
    hud_clean = hud_clean.rename(
        columns={
            "stusps": "state",
            "countyname": "county",
            "fmr_1": "fmr_1br",
            "fmr_2": "fmr_2br",
            "fmr_3": "fmr_3br",
            }
        )

    hud_clean["state"] = hud_clean["state"].astype(str).str.strip().str.lower()
    hud_clean["county"] = normalize_county(hud_clean["county"])
    hud_clean["fips"] = clean_hud_fips(hud_clean["fips"])

    hud_clean["fmr_1br"] = pd.to_numeric(hud_clean["fmr_1br"], errors="coerce")
    hud_clean["fmr_2br"] = pd.to_numeric(hud_clean["fmr_2br"], errors="coerce")
    hud_clean["fmr_3br"] = pd.to_numeric(hud_clean["fmr_3br"], errors="coerce")

    # Build HUD lookup for assigning FIPS to Zillow
    hud_lookup = hud_clean[["state", "county", "fips"]].drop_duplicates()

    # Merge FIPS into Zillow
    zillow_clean = zillow_clean.merge(
    hud_lookup,
    on=["state", "county"],
    how="left"
    )
    # Match stats
    matched = zillow_clean["fips"].notna().sum()
    unmatched = zillow_clean["fips"].isna().sum()

    print(f"\nZillow rows matched to FIPS: {matched}")
    print(f"Zillow rows without FIPS match: {unmatched}")

    if unmatched > 0:
        print("\nSample unmatched Zillow counties:")
        print(
            zillow_clean[zillow_clean["fips"].isna()][["state", "county"]]
            .drop_duplicates()
            .head(10)
            .to_string(index=False)
            )

    # Remove duplicates
    zillow_clean = zillow_clean.drop_duplicates()
    hud_clean = hud_clean.drop_duplicates()

    # show a preview of the cleaned dataframes
    print("\nCleaned Zillow preview before normalization:")
    print(zillow_clean.head(5))
    print("\nCleaned HUD preview before normalization:")
    print(hud_clean.head(5))

    return zillow_clean, hud_clean

# Define a function to build the ACS API request
def build_acs_request() -> tuple[str, dict]:
    """
    Build the ACS API endpoint and query parameters.
    """
    url = f"{BASE_URL}/{YEAR}/{DATASET}"
    params = {
        "get": ",".join(VARIABLES),
        "for": GEOGRAPHY,
    }
    return url, params

# Function to fetch raw acs data from the API
def fetch_acs_data() -> pd.DataFrame:
    """
    Request ACS county-level income data from the Census API
    and return it as a cleaned DataFrame.
    """
    url, params = build_acs_request()

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    df = pd.DataFrame(data[1:], columns=data[0])

    return df

# Function to clean the raw ACS data
def clean_acs_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean ACS data and create a 5-digit county FIPS code.
    """
    df = df.rename(columns={
        "NAME": "county_full_name",
        "B19013_001E": "median_household_income",
        "state": "state_fips",
        "county": "county_fips",
    })

    # Create combined county FIPS code
    df["fips"] = df["state_fips"].str.zfill(2) + df["county_fips"].str.zfill(3)

    # Convert income to numeric
    df["median_household_income"] = pd.to_numeric(
        df["median_household_income"], errors="coerce"
    )

    # Optional: split county/state name for readability
    name_parts = df["county_full_name"].str.split(",", n=1, expand=True)
    df["county_name"] = name_parts[0].str.strip().str.lower()
    df["state_name"] = name_parts[1].str.strip().str.lower() if name_parts.shape[1] > 1 else None

    # Keep only useful fields
    df = df[
        [
            "fips",
            "state_fips",
            "county_fips",
            "county_full_name",
            "county_name",
            "state_name",
            "median_household_income",
        ]
    ].drop_duplicates()

    return df

def fetch_clean_save_acs_data() -> pd.DataFrame:
    """
    Fetch raw ACS data, clean it, and save to CSV.
    """
    print("Fetching ACS data from Census API...")
    raw_df = fetch_acs_data()
    print("Cleaning ACS data...")
    clean_df = clean_acs_data(raw_df)
    print(f"Saving cleaned ACS data to {output_acs_csv}...")
    clean_df.to_csv(output_acs_csv, index=False)
    print("ACS data fetched, cleaned, and saved successfully.")
    return clean_df

def load_state_info(conn, acs_df):
    """
    Load state information into the state_info table.
    """
    print("Loading state information into state_info table...")
    state_info_df = acs_df[["state_fips", "state_name"]].drop_duplicates()
    state_info_df.to_sql("state_info", conn, if_exists="append", index=False)
    # Save state_info to a separate CSV for reference
    state_info_csv = BASE_DIR / "state_info.csv"
    state_info_df.to_csv(state_info_csv, index=False)
    print(f"Loaded {len(state_info_df)} states into state_info table and saved to {state_info_csv}.")
    # Verify load by querying the table and showing a sample
    state_count = conn.execute("SELECT COUNT(*) FROM state_info").fetchone()[0]
    print(f"\nLoaded {state_count} rows into state_info table.")
    print("Sample state_info data:")
    state_info_sample = pd.read_sql_query("SELECT * FROM state_info LIMIT 5", conn)
    print(state_info_sample)
    return None

def load_county_info(conn, acs_df):
    """
    Load county information into the county_info table.
    """
    print("Loading county information into county_info table...")
    county_info_df = acs_df[["fips", "county_name", "state_fips"]].drop_duplicates()
    county_info_df.to_sql("county_info", conn, if_exists="append", index=False)
    # Save county_info to a separate CSV for reference
    county_info_csv = BASE_DIR / "county_info.csv"
    county_info_df.to_csv(county_info_csv, index=False)
    print(f"Loaded {len(county_info_df)} counties into county_info table and saved to {county_info_csv}.")
    # Verify load by querying the table and showing a sample
    county_count = conn.execute("SELECT COUNT(*) FROM county_info").fetchone()[0]
    print(f"\nLoaded {county_count} rows into county_info table.")
    print("Sample county_info data:")
    county_info_sample = pd.read_sql_query("SELECT * FROM county_info LIMIT 5", conn)
    print(county_info_sample)
    return None

def load_zip_info(conn, zillow_df):
    """
    Load zip code information into the zip_info table.
    """
    print("Loading zip code information into zip_info table...")
    zip_info_df = zillow_df[["zip", "city", "metro", "median_home_value", "fips"]].drop_duplicates()
    zip_info_df.to_sql("zip_info", conn, if_exists="append", index=False)
    # Save zip_info to a separate CSV for reference
    zip_info_csv = BASE_DIR / "zip_info.csv"
    zip_info_df.to_csv(zip_info_csv, index=False)
    print(f"Loaded {len(zip_info_df)} zip codes into zip_info table and saved to {zip_info_csv}.")
    # Verify load by querying the table and showing a sample
    zip_info_count = conn.execute("SELECT COUNT(*) FROM zip_info").fetchone()[0]
    print(f"\nLoaded {zip_info_count} rows into table: zip_info")
    zip_info_preview = pd.read_sql_query("SELECT * FROM zip_info LIMIT 5", conn)
    print("zip_info preview:")
    print(zip_info_preview.to_string(index=False))
    return None

def load_hud_rent_info(conn, hud_df):
    """
    Load HUD rent information into the hud_rent_info table.
    """
    print("Loading HUD rent information into hud_rent_info table...")
    hud_rent_info_df = hud_df[["hud_area_name", "fips", "fmr_1br", "fmr_2br", "fmr_3br"]].drop_duplicates()
    hud_rent_info_df.to_sql("hud_rent_info", conn, if_exists="append", index=False)
    # Save hud_rent_info to a separate CSV for reference
    hud_rent_info_csv = BASE_DIR / "hud_rent_info.csv"
    hud_rent_info_df.to_csv(hud_rent_info_csv, index=False)
    print(f"Loaded {len(hud_rent_info_df)} HUD rent records into hud_rent_info table and saved to {hud_rent_info_csv}.")
    # Verify load by querying the table and showing a sample
    hud_count = conn.execute("SELECT COUNT(*) FROM hud_rent_info").fetchone()[0]
    print(f"\nLoaded {hud_count} rows into hud_rent_info table.")
    print("Sample hud_rent_info data:")
    hud_rent_info_sample = pd.read_sql_query("SELECT * FROM hud_rent_info LIMIT 5", conn)
    print(hud_rent_info_sample)
    return None

def load_acs_income_info(conn, acs_df):
    """
    Load ACS income information into the acs_income_info table.
    """
    print("Loading ACS income information into acs_income_info table...")
    acs_income_info_df = acs_df[["fips", "median_household_income"]].drop_duplicates()
    acs_income_info_df.to_sql("acs_income_info", conn, if_exists="append", index=False)
    # Save acs_income_info to a separate CSV for reference
    acs_income_info_csv = BASE_DIR / "acs_income_info.csv"
    acs_income_info_df.to_csv(acs_income_info_csv, index=False)
    print(f"Loaded {len(acs_income_info_df)} ACS income records into acs_income_info table and saved to {acs_income_info_csv}.")
    # Verify load by querying the table and showing a sample
    income_count = conn.execute("SELECT COUNT(*) FROM acs_income_info").fetchone()[0]
    print(f"\nLoaded {income_count} rows into acs_income_info table.")
    print("Sample acs_income_info data:")
    acs_income_info_sample = pd.read_sql_query("SELECT * FROM acs_income_info LIMIT 5", conn)
    print(acs_income_info_sample)
    return None

def csv_load_wrapper(conn):
    """
    Wrapper function to load and clean source CSVs, then load into SQLite.
    """
    zillow_clean, hud_clean = load_and_clean_csvs()
    # fetch the ACS data from the API, clean it, and save to CSV
    acs_df = fetch_clean_save_acs_data()
    # Load state_info and county_info first since other tables reference them
    load_state_info(conn, acs_df)
    load_county_info(conn, acs_df)
    # Load zip_info, hud_rent_info, and acs_income next since 
    # they reference county_info
    load_zip_info(conn, zillow_clean)
    load_hud_rent_info(conn, hud_clean)
    load_acs_income_info(conn, acs_df)

def main():
    # Connect to SQLite database
    conn = sqlite3.connect(DB_PATH)
    print('Loading source data from CSVs and API, cleaning it, and loading into SQLite...')
    print(f"Connected to SQLite database at {DB_PATH}.")

    # Load data from CSVs and API, clean it, and load into SQLite
    csv_load_wrapper(conn)

    # Commit changes to the database
    conn.commit()
    # Close the connection
    conn.close()
    print("SQLite connection closed.")

if __name__ == "__main__":
    main()


