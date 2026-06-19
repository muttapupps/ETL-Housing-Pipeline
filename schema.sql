-- HOUSING PIPELINE DATABASE SCHEMA

-- Drop tables if they already exist (for clean rebuild)
DROP TABLE IF EXISTS affordability_metrics;
DROP TABLE IF EXISTS acs_income_info;
DROP TABLE IF EXISTS hud_rent_info;
DROP TABLE IF EXISTS zip_info;
DROP TABLE IF EXISTS county_info;
DROP TABLE IF EXISTS affordability_tiers;
DROP TABLE IF EXISTS state_info;

-- STATE TABLE
CREATE TABLE state_info (
    state_fips VARCHAR(2) PRIMARY KEY,
    state_name TEXT
);

-- AFFORDABILITY TIERS TABLE
CREATE TABLE affordability_tiers (
    tier_id INTEGER PRIMARY KEY,
    tier_name TEXT,
    description TEXT
);

-- COUNTY TABLE
CREATE TABLE county_info (
    fips VARCHAR(5) PRIMARY KEY,
    county_name TEXT,
    state_fips VARCHAR(2),
    FOREIGN KEY (state_fips) REFERENCES state_info(state_fips)
);

-- ZIP TABLE
CREATE TABLE zip_info (
    zip VARCHAR(5) PRIMARY KEY,
    city TEXT,
    metro TEXT,
    median_home_value NUMERIC,
    fips VARCHAR(5),
    FOREIGN KEY (fips) REFERENCES county_info(fips)
);

-- HUD RENT TABLE
CREATE TABLE hud_rent_info (
    hud_area_name TEXT,
    fips VARCHAR(5),
    fmr_1br NUMERIC,
    fmr_2br NUMERIC,
    fmr_3br NUMERIC,
    PRIMARY KEY (hud_area_name, fips),
    FOREIGN KEY (fips) REFERENCES county_info(fips)
);

-- ACS INCOME TABLE
CREATE TABLE acs_income_info (
    fips VARCHAR(5) PRIMARY KEY,
    median_household_income NUMERIC,
    FOREIGN KEY (fips) REFERENCES county_info(fips)
);

-- AFFORDABILITY METRICS TABLE
CREATE TABLE affordability_metrics (
    zip VARCHAR(5) PRIMARY KEY,
    price_to_income_ratio NUMERIC,
    rent_to_home_value_ratio NUMERIC,
    annual_rent_to_income_ratio NUMERIC,
    affordability_index NUMERIC,
    affordability_tier INTEGER,
    FOREIGN KEY (zip) REFERENCES zip_info(zip),
    FOREIGN KEY (affordability_tier) REFERENCES affordability_tiers(tier_id)
);
