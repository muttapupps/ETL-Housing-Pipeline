from flask import Flask, jsonify, request
import sqlite3
import pandas as pd
from pathlib import Path

# Create our Flask app
app = Flask(__name__)

# Establish base directory
BASE_DIR = Path(__file__).resolve().parent

# Create a test route to verify the API is working
@app.route("/")
def test():
    return jsonify({"message": "Housing API is running.", "status": "ok"})

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

# Create an endpoint to initialize the database loading pipeline
@app.route('/housing_api/initialize', methods=['POST'])
def initialize():
    """Endpoint to trigger the database initialization and metrics computation."""
    # Run python scripts to create tables, load data, and compute metrics
    try:
        # Run the create_tables.py script
        from create_tables import main as run_create_tables
        from load_source_data import main as run_load_source_data
        from compute_and_load_metrics import main as run_compute_and_load_metrics
        from create_affordability_view import main as run_create_affordability_view
        run_create_tables()
        run_load_source_data()
        run_compute_and_load_metrics()
        run_create_affordability_view()
        return jsonify({"message": "Database initialized and metrics computed successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Create an endpoint to retrieve affordability metrics for a given zipcode
@app.route('/housing_api/metrics/<zip_code>', methods=['GET'])
def get_metrics(zip_code):
    try:
        conn = sqlite3.connect(BASE_DIR / "housing_final.db")
        cursor = conn.cursor()
        # query affordability view for the given zip code
        query = '''
        SELECT * FROM zip_affordability_view
        WHERE zip = ?
        '''
        cursor.execute(query, (zip_code,))
        row = cursor.fetchone()
        conn.close()
        if row:
            # Return a format that preserves the column names for clarity
            columns = ["zip", "city", "state_name", "median_home_value",
                        "fmr_1br", "fmr_2br", "fmr_3br", "median_household_income", 
                        "affordability_index", "tier_description"]
            metrics = dict(zip(columns, row))
            return jsonify({"metrics": metrics}), 200
        else:
            return jsonify({"error": "Metrics not found for the given zip code."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Create an endpoint to retrieve a specified number of zip codes with the 
# highest affordability index in a given state and export the results to a CSV file
@app.route('/housing_api/top_affordable_zips/<state>/<int:limit>', methods=['GET'])
def get_top_affordable_zips(state, limit):
    try:
        conn = sqlite3.connect(BASE_DIR / "housing_final.db")
        cursor = conn.cursor()
        query = '''
        SELECT * FROM zip_affordability_view
        WHERE state_name = ?
        ORDER BY affordability_index DESC
        LIMIT ?
        '''
        cursor.execute(query, (state, limit))
        rows = cursor.fetchall()
        conn.close()
        if rows:
            columns = ["zip", "city", "state_name", "median_home_value",
                        "fmr_1br", "fmr_2br", "fmr_3br", "median_household_income", 
                        "affordability_index", "tier_description"]
            results = [dict(zip(columns, row)) for row in rows]
            # Export results to CSV
            df = pd.DataFrame(results)
            csv_path = BASE_DIR / f"top_{limit}_affordable_zips_{state}.csv"
            df.to_csv(csv_path, index=False)
            return jsonify({"top_affordable_zips": results, "csv_path": str(csv_path)}), 200
        else:
            return jsonify({"error": "No zip codes found for the given state."}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Initialize the Flask app
if __name__ == '__main__':
    port = 8001
    app.run(debug=True, port=port)
    