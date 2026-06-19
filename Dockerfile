FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["sh", "-c", "python create_tables.py && python load_source_data.py && python compute_and_load_metrics.py && python create_affordability_view.py && python housing_api.py"]
