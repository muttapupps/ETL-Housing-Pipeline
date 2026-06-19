# ETL Housing Pipeline

A data engineering pipeline and REST API for analyzing U.S. housing affordability by zip code, combining Zillow home value data, HUD Fair Market Rent data, and U.S. Census ACS income data.

---

## What This Project Does

This project answers the question: **"How affordable is housing in any U.S. zip code?"**

It pulls data from three sources, cleans and joins them into a normalized SQLite database, computes an affordability index for every zip code, and exposes the results through a Flask REST API.

---

## Architecture

```
Data Sources
    ├── Zillow CSV         → Median home values by zip code
    ├── HUD CSV            → Fair Market Rents by county
    └── Census ACS API     → Median household income by county
            │
            ▼
    load_source_data.py    → Cleans and loads data into SQLite
            │
            ▼
    compute_and_load_metrics.py  → Calculates affordability index
            │
            ▼
    create_affordability_view.py → Creates SQL view for easy querying
            │
            ▼
    housing_api.py         → Flask REST API exposes the results
```

---

## Affordability Index

The affordability index is calculated using two weighted ratios:

- **Price-to-Income Ratio** (60% weight): Median home value / Median household income
- **Rent-to-Income Ratio** (40% weight): Annual 2BR rent / Median household income

A **higher index = more affordable**. Zip codes are then assigned to one of five tiers:

| Tier | Label | Description |
|------|-------|-------------|
| 5 | Very Affordable | Top 10% most affordable |
| 4 | Above Average | 60th–90th percentile |
| 3 | Average | 40th–60th percentile |
| 2 | Below Average | 10th–40th percentile |
| 1 | Very Unaffordable | Bottom 10% |

---

## Database Schema

```
state_info ──── county_info ──── zip_info
                    │                │
               hud_rent_info    affordability_metrics
               acs_income_info       │
                                affordability_tiers
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/housing_api/initialize` | Run full pipeline and load database |
| GET | `/health` | Check API health |
| GET | `/housing_api/metrics/<zip>` | Get affordability metrics for a zip code |
| GET | `/housing_api/top_affordable_zips/<state>/<limit>` | Top N most affordable zips in a state |

### Example Response — `/housing_api/metrics/30301`

```json
{
  "metrics": {
    "zip": "30301",
    "city": "Atlanta",
    "state_name": "Georgia",
    "median_home_value": 320000,
    "fmr_1br": 1200,
    "fmr_2br": 1450,
    "fmr_3br": 1800,
    "median_household_income": 65000,
    "affordability_index": 14.23,
    "tier_description": "Below Average Affordability"
  }
}
```

---

## Project Structure

```
├── housing_api.py                  # Flask REST API
├── load_source_data.py             # Ingests and cleans source data
├── compute_and_load_metrics.py     # Computes affordability metrics
├── create_affordability_view.py    # Creates SQL view
├── create_tables.py                # Sets up database schema
├── api_client.py                   # CLI client for the API
├── schema.sql                      # Database schema reference
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Docker setup
└── docker-compose.yml              # Docker Compose config
```

---

## Setup & Running

### Option 1: Docker (Recommended)

```bash
docker-compose up --build
```

### Option 2: Local

```bash
pip install -r requirements.txt
python housing_api.py
```

Then initialize the database:
```bash
python api_client.py --initialize_db
```

### Query a zip code:
```bash
python api_client.py --zip_metrics 10001
```

### Get top 10 most affordable zip codes in Georgia:
```bash
python api_client.py --top_zips "Georgia,10"
```

---

## Data Sources

- [Zillow Research Data](https://www.zillow.com/research/data/) — Median home values by zip code
- [HUD Fair Market Rents](https://www.huduser.gov/portal/datasets/fmr.html) — Fair market rents by county
- [U.S. Census Bureau ACS](https://www.census.gov/data/developers/data-sets/acs-5year.html) — Median household income by county (2022)
