"""Database schema definition for TimescaleDB"""

import logging
from app.database.connection import create_db_connection

logger = logging.getLogger("options_etl.schema")

def initialize_database():
    """
    Initialize the TimescaleDB database with the necessary tables and hypertables.
    This should be run once to set up the database.
    
    Creates:
        - market_metrics table/hypertable
        - options_data table/hypertable
        - Indexes for optimized queries
        - Views for common queries (like latest metrics)
    """
    conn = create_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create the extension if it doesn't exist
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
        
        # Create market_metrics table for spot price and other metrics
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_metrics (
            timestamp TIMESTAMPTZ NOT NULL,
            symbol VARCHAR(10) NOT NULL,
            spot_price NUMERIC NOT NULL,
            prev_day_close NUMERIC,
            price_change NUMERIC,
            price_change_pct NUMERIC,
            PRIMARY KEY (timestamp, symbol)
        );
        """)
        
        # Create options_data table for the filtered options data
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS options_data (
            timestamp TIMESTAMPTZ NOT NULL,
            symbol VARCHAR(10) NOT NULL,
            option_type VARCHAR(4) NOT NULL,  -- 'CALL' or 'PUT'
            option_symbol VARCHAR(50) NOT NULL,
            expiration_date TIMESTAMPTZ NOT NULL,
            strike_price NUMERIC NOT NULL,
            iv NUMERIC,
            delta NUMERIC,
            gamma NUMERIC,
            open_interest INTEGER,
            volume INTEGER,
            gamma_exposure NUMERIC,
            time_till_exp NUMERIC,
            PRIMARY KEY (timestamp, option_symbol)
        );
        """)
        
        # Convert tables to hypertables
        cursor.execute("""
        SELECT create_hypertable('market_metrics', 'timestamp', if_not_exists => TRUE);
        """)
        
        cursor.execute("""
        SELECT create_hypertable('options_data', 'timestamp', if_not_exists => TRUE);
        """)
        
        # Create indexes for faster queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_mm_symbol ON market_metrics (symbol, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_od_symbol_expiry ON options_data (symbol, expiration_date, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_od_strike ON options_data (strike_price);
        """)
        
        # Create a view for latest market metrics
        cursor.execute("""
        CREATE OR REPLACE VIEW latest_market_metrics AS
        SELECT DISTINCT ON (symbol) *
        FROM market_metrics
        ORDER BY symbol, timestamp DESC;
        """)
        
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()