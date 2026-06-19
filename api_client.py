import argparse
import requests

BASE_URL = "http://localhost:8001"

def check_api_health():
    """Check the health of the API by sending a GET request to the /health endpoint."""
    url = f"{BASE_URL}/health"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print("API is healthy.")
            print("Response:", response.json())
        else:
            print(f"API health check failed. Status code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"An error occurred while checking API health: {e}")

def initialize_database():
    """Send a POST request to the API endpoint to initialize the database."""
    url = f"{BASE_URL}/housing_api/initialize"
    try:
        response = requests.post(url)
        if response.status_code == 200:
            print("Database initialized successfully.")
            print("Response:", response.json())
        else:
            print(f"Failed to initialize database. Status code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"An error occurred while initializing the database: {e}")

def get_zip_metrics(zip_code):
    """Send a GET request to retrieve affordability metrics for a given zip code."""
    url = f"{BASE_URL}/housing_api/metrics/{zip_code}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Affordability metrics for zip code {zip_code}:")
            # Parse and print the JSON response in a readable format
            # Extract the metrics dictionary from the response JSON
            metrics = response.json()['metrics']
            print(f"City: {metrics['city']}")
            print(f"State: {metrics['state_name']}")
            print(f"Median Home Value: ${metrics['median_home_value']:.2f}")
            print(f"FMR 1BR: ${metrics['fmr_1br']}")
            print(f"FMR 2BR: ${metrics['fmr_2br']}")
            print(f"FMR 3BR: ${metrics['fmr_3br']}")
            print(f"Median Household Income: ${metrics['median_household_income']}")
            print(f"Affordability Index: {metrics['affordability_index']:.2f}")
            print(f"Affordability Description: {metrics['tier_description']}")
        else:
            print(f"Failed to retrieve metrics for zip code {zip_code}. Status code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"An error occurred while retrieving metrics for zip code {zip_code}: {e}")

def get_top_zips(state, limit):
    """Send a GET request to retrieve the top affordable zip codes for a given state."""
    url = f"{BASE_URL}/housing_api/top_affordable_zips/{state}/{limit}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Top {limit} affordable zip codes in {state}:")
            # Parse and print the JSON response in a readable format
            zips = response.json()['top_affordable_zips']
            for zip_info in zips:
                print(f"Zip Code: {zip_info['zip']}, City: {zip_info['city']}, Affordability Index: {zip_info['affordability_index']:.2f}")
            print(f"Results saved to top_{limit}_affordable_zips_{state}.csv")
        else:
            print(f"Failed to retrieve top affordable zip codes for state {state}. Status code: {response.status_code}")
            print("Response:", response.text)
    except Exception as e:
        print(f"An error occurred while retrieving top affordable zip codes for state {state}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="API Client for Housing Pipeline")
    parser.add_argument("--initialize_db", action="store_true", help="Initialize the database")
    parser.add_argument("--health", action="store_true", help="Check the health of the API")
    parser.add_argument("--zip_metrics", type=str, help="Retrieve affordability metrics for a given zip code")
    parser.add_argument("--top_zips", type=str, help="Retrieve top affordable zip codes for a given state and limit (format: 'state,limit')")
    args = parser.parse_args()

    if args.initialize_db:
        initialize_database()
    elif args.health:
        check_api_health()
    elif args.zip_metrics:
        get_zip_metrics(args.zip_metrics)
    elif args.top_zips:
        state, limit = args.top_zips.split(",")
        get_top_zips(state.strip(), int(limit.strip()))