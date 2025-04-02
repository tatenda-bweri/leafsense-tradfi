# LeafSense Options Analytics Platform

LeafSense is an options analytics platform that provides market metrics and gamma exposure analysis for options trading. The platform includes an ETL pipeline to fetch, process, and load options data into a TimescaleDB database, and a web interface to visualize the data.

## Project Structure

```
-- app/
  |-- __init__.py
  |-- database/
    |-- __init__.py
    |-- connection.py          # Database connection utilities
    |-- schema.py             # Database schema definition
  |-- etl/
    |-- __init__.py
    |-- fetch.py              # Data fetching functions
    |-- process.py            # Data processing/transformation
    |-- load.py               # Data loading to database
    |-- run.py                # Main ETL runner
  |-- models/
    |-- __init__.py
    |-- options.py            # Options data models
    |-- market.py             # Market metrics models
  |-- api/
    |-- __init__.py
    |-- routes.py             # API endpoints for frontend
  |-- services/
    |-- __init__.py
    |-- options_service.py    # Business logic for options data
    |-- metrics_service.py    # Business logic for market metrics
  |-- utils/
    |-- __init__.py
    |-- date_utils.py         # Date handling utilities
    |-- logging_utils.py      # Logging utilities
-- config/
  |-- __init__.py
  |-- settings.py             # Application settings
-- web/
  |-- static/
    |-- css/
    |-- js/
    |-- img/
  |-- templates/
    |-- index.html
    |-- dashboard.html
-- tests/
  |-- __init__.py
  |-- test_etl.py
  |-- test_api.py
-- main.py                    # Application entry point
-- scheduler.py               # ETL scheduling script
-- requirements.txt
-- .env.example
-- .gitignore
-- README.md
```

## Setup

1. Clone the repository:

   ```sh
   git clone https://github.com/yourusername/leavesense.git
   cd leavesense
   ```

2. Create a virtual environment and activate it:

   ```sh
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:

   ```sh
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on the `.env.example` file and configure your environment variables.

5. Initialize the database:

   ```sh
   python main.py init_db
   ```

6. Run the ETL scheduler:

   ```sh
   python scheduler.py
   ```

7. Start the Django development server:
   ```sh
   python main.py runserver
   ```

## Usage

- Access the web interface at `http://localhost:8000`.
- Use the dashboard to view market metrics and gamma exposure charts.

## Testing

Run the tests using:

```sh
python -m unittest discover tests
```

License
This project is licensed under the MIT License.
