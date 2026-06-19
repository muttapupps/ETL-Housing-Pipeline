from pathlib import Path
import pandas as pd
import sqlite3

# Base directory so paths work inside Docker
BASE_DIR = Path(__file__).resolve().parent

# File paths
DB_PATH = BASE_DIR / "housing_final.db"

def create_tier_df() -> pd.DataFrame:
    """Create a DataFrame with tier information."""
    tiers = [
    {'tier_id': 1, 'tier_name': 'Very Unaffordable', 'description': 'Less affordable than 90%% of zipcodes'},
    {'tier_id': 2, 'tier_name': 'Below Average Affordability', 'description': 'Between 10th and 40th percentile affordability'},
    {'tier_id': 3, 'tier_name': 'Average Affordability', 'description': 'Between 40th and 60th percentile affordability'},
    {'tier_id': 4, 'tier_name': 'Above Average Affordability', 'description': 'Between 60th and 90th percentile affordability'},
    {'tier_id': 5, 'tier_name': 'Very Affordable', 'description': 'More affordable than 90%% of zipcodes'}
    ]
    tiers_df = pd.DataFrame(tiers)

    return tiers_df

def load_tiers_to_db(tiers_df: pd.DataFrame, conn: sqlite3.Connection):
    """Load the tiers DataFrame into the database."""
    print("Loading affordability tiers into the database...")
    tiers_df.to_sql('affordability_tiers', conn, if_exists='replace', index=False)

    # Show the table to ensure loading worked as intended
    print("Affordability tiers loaded. Data:")
    tiers_sample = pd.read_sql_query("SELECT * FROM affordability_tiers LIMIT 5", conn)
    print(tiers_sample)

    # Save tiers to csv for reference
    tiers_df.to_csv(BASE_DIR / "affordability_tiers.csv", index=False)
    print(f"Affordability tiers saved to {BASE_DIR / 'affordability_tiers.csv'}")
    return None

def generate_metrics(conn: sqlite3.Connection):
    """
    Generate affordability metrics and return a DataFrame with the results.
    This function performs the necessary SQL joins to gather all relevant data, 
    calculates the affordability metrics, and returns a DataFrame sorted by 
    affordability index.
    """
    # To load the metrics data, we first need to calculate it
    metrics_join_query = """
    SELECT
        z.zip,
        z.city,
        z.fips,
        z.median_home_value,
        h.fmr_1br,
        h.fmr_2br,
        h.fmr_3br,
        a.median_household_income,
        c.county_name,
        s.state_name
    FROM zip_info z
    JOIN hud_rent_info h
        ON z.fips = h.fips
    JOIN acs_income_info a
        ON z.fips = a.fips
    JOIN county_info c
        ON z.fips = c.fips
    JOIN state_info s
        ON c.state_fips = s.state_fips
    """

    df_metrics = pd.read_sql_query(metrics_join_query, conn)

    df_metrics["price_to_income_ratio"] = df_metrics["median_home_value"] / df_metrics["median_household_income"]
    df_metrics["annual_rent_to_income_ratio"] = (df_metrics["fmr_2br"] * 12) / df_metrics["median_household_income"]
    df_metrics["rent_to_home_value_ratio"] = (df_metrics["fmr_2br"] * 12) / df_metrics["median_home_value"]

    # Optional combined affordability score
    raw_score = (
        0.6 * df_metrics["price_to_income_ratio"] +
        0.4 * df_metrics["annual_rent_to_income_ratio"]
    )

    # Convert so HIGHER = BETTER
    df_metrics["affordability_index"] = 100 / raw_score

    # Sort highest first
    df_metrics = df_metrics.sort_values("affordability_index", ascending=False)
    print("Affordability Metrics Before Processing and Normalization:")
    print(df_metrics[[
        "zip",
        "city",
        "state_name",
        "county_name",
        "fips",
        "price_to_income_ratio",
        "annual_rent_to_income_ratio",
        "rent_to_home_value_ratio",
        "affordability_index"
    ]].head(20).to_string(index=False))

    return df_metrics

def process_metrics_df(df_metrics: pd.DataFrame) -> pd.DataFrame:
    """Process the metrics DataFrame to assign affordability tiers."""
    # Calculate percentiles for affordability index
    df_metrics["affordability_percentile"] = df_metrics["affordability_index"].rank(pct=True)

    df_metrics = df_metrics.dropna(subset=['affordability_index'])
    new_na_count = df_metrics['affordability_index'].isna().sum()
    print(f'Number of NA values after cleaning {new_na_count}')

    # aggregate by zip code to ensure one entry per zip code, taking the mean of the 
    # affordability metrics for any duplicate zip codes, assuming that different entries
    # for the same zip code will be similar enough that taking the mean is a reasonable 
    # way to create a single entry for each zip code for loading into the database. 
    # This will allow us to load the data without errors related to duplicate primary keys, 
    # and we can integrate New England townships separately if we want to in the future since 
    # they have unique HUD codes that can be joined on.
    df_metrics_slim = df_metrics[[
        "zip",
        "price_to_income_ratio",
        "annual_rent_to_income_ratio",
        "rent_to_home_value_ratio",
        "affordability_index"
    ]].copy()
    df_metrics_slim = df_metrics_slim.groupby("zip").mean().reset_index()
    # Check for duplicate zip codes in the slimmed metrics data
    duplicate_zip_count = df_metrics_slim['zip'].duplicated().sum()
    print(f"\nNumber of duplicate zip codes in processed metrics data: {duplicate_zip_count}")

    # Assign tiers
    df_metrics_slim['affordability_tier'] = pd.cut(
        df_metrics_slim['affordability_index'].rank(pct=True),
        [0, 0.1, 0.4, 0.6, 0.9, 1],
        labels=[1, 2, 3, 4, 5],
        include_lowest=True
    ).astype(int)
    print("\nAffordability Index Tiers Assigned.")
    return df_metrics_slim

def load_metrics_to_db(df_metrics: pd.DataFrame, conn: sqlite3.Connection):
    """Load the processed metrics DataFrame into the database."""
    print("Loading affordability metrics into the database...")
    df_metrics.to_sql('affordability_metrics', conn, if_exists='append', index=False)

    # Check load success by querying the length and a sample
    metrics_count = conn.execute("SELECT COUNT(*) FROM affordability_metrics").fetchone()[0]
    print(f"\nLoaded {metrics_count} rows into affordability_metrics table.")
    metrics_sample = pd.read_sql_query("SELECT * FROM affordability_metrics LIMIT 5", conn)
    print("Sample affordability_metrics data:")
    print(metrics_sample)

    # Save metrics to csv for reference
    df_metrics.to_csv(BASE_DIR / "affordability_metrics.csv", index=False)
    print(f"Affordability metrics saved to {BASE_DIR / 'affordability_metrics.csv'}")
    return None

def main():
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)

    # Create and load tiers
    tiers_df = create_tier_df()
    load_tiers_to_db(tiers_df, conn)

    # Generate, process, and load metrics
    df_metrics = generate_metrics(conn)
    df_metrics_processed = process_metrics_df(df_metrics)
    load_metrics_to_db(df_metrics_processed, conn)

    # Commit changes to the database
    conn.commit()
    # Close the database connection
    conn.close()

if __name__ == "__main__":
    main()