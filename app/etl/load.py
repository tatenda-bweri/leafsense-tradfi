"""Data loading functions for options analytics database"""

from psycopg2.extras import execute_values
from app.database.connection import create_db_connection, create_cursor, close_connection
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

def transform_options_data(filtered_data, timestamp):
    """
    Transform options data for database insertion
    
    Args:
        filtered_data: Processed options data
        timestamp: Timestamp for the data
        
    Returns:
        List of records ready for database insertion
    """
    records = []
    symbol = "_SPX"  # Default symbol
    
    try:
        # Process each row in the filtered data
        for _, row in filtered_data.iterrows():
            # Create call record
            if row.get('calls') and row.get('call_gamma') is not None:
                call_record = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'option_type': 'CALL',
                    'option_symbol': row['calls'],
                    'expiration_date': row['expiration_date'],
                    'strike_price': row['strike_price'],
                    'iv': row.get('call_iv'),
                    'delta': row.get('call_delta'),
                    'gamma': row.get('call_gamma'),
                    'open_interest': row.get('call_open_interest'),
                    'volume': row.get('call_volume'),
                    'gamma_exposure': row.get('call_gamma_exposure'),
                    'time_till_exp': row.get('time_till_exp')
                }
                records.append(call_record)
            
            # Create put record
            if row.get('puts') and row.get('put_gamma') is not None:
                put_record = {
                    'timestamp': timestamp,
                    'symbol': symbol,
                    'option_type': 'PUT',
                    'option_symbol': row['puts'],
                    'expiration_date': row['expiration_date'],
                    'strike_price': row['strike_price'],
                    'iv': row.get('put_iv'),
                    'delta': row.get('put_delta'),
                    'gamma': row.get('put_gamma'),
                    'open_interest': row.get('put_open_interest'),
                    'volume': row.get('put_volume'),
                    'gamma_exposure': row.get('put_gamma_exposure'),
                    'time_till_exp': row.get('time_till_exp')
                }
                records.append(put_record)
                
        logger.info(f"Transformed {len(records)} options records for database insertion")
        return records
    
    except Exception as e:
        logger.error(f"Error transforming options data: {str(e)}")
        raise Exception(f"Failed to transform options data: {str(e)}")

def load_market_metrics(market_metrics, timestamp):
    """
    Load market metrics data into database
    
    Args:
        market_metrics: Dictionary with market metrics
        timestamp: Timestamp for the data
        
    Returns:
        Success status
    """
    connection = None
    cursor = None
    
    try:
        # Create database connection and cursor
        connection = create_db_connection()
        cursor = create_cursor(connection)
        
        # Insert market metrics
        insert_query = """
        INSERT INTO market_metrics 
        (timestamp, symbol, spot_price, prev_day_close, price_change, price_change_pct)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (timestamp, symbol) 
        DO UPDATE SET 
            spot_price = EXCLUDED.spot_price,
            prev_day_close = EXCLUDED.prev_day_close,
            price_change = EXCLUDED.price_change,
            price_change_pct = EXCLUDED.price_change_pct
        """
        
        cursor.execute(
            insert_query, 
            (
                timestamp,
                market_metrics['symbol'],
                market_metrics['spot_price'],
                market_metrics['prev_day_close'],
                market_metrics['price_change'],
                market_metrics['price_change_pct']
            )
        )
        
        logger.info(f"Market metrics loaded successfully for {market_metrics['symbol']} at {timestamp}")
        return True
        
    except Exception as e:
        logger.error(f"Error loading market metrics: {str(e)}")
        return False
        
    finally:
        # Close connection
        close_connection(connection, cursor)

def load_options_data(options_records):
    """
    Load options data into database
    
    Args:
        options_records: List of options data records
        
    Returns:
        Success status
    """
    if not options_records:
        logger.warning("No options records to load")
        return False
    
    connection = None
    cursor = None
    
    try:
        # Create database connection and cursor
        connection = create_db_connection()
        cursor = create_cursor(connection)
        
        # Insert options data using execute_values for better performance
        insert_query = """
        INSERT INTO options_data (
            timestamp, symbol, option_type, option_symbol, expiration_date, 
            strike_price, iv, delta, gamma, open_interest, volume, 
            gamma_exposure, time_till_exp
        ) VALUES %s
        ON CONFLICT (timestamp, option_symbol) 
        DO UPDATE SET 
            iv = EXCLUDED.iv,
            delta = EXCLUDED.delta,
            gamma = EXCLUDED.gamma,
            open_interest = EXCLUDED.open_interest,
            volume = EXCLUDED.volume,
            gamma_exposure = EXCLUDED.gamma_exposure
        """
        
        # Prepare values for batch insert
        values = [
            (
                record['timestamp'],
                record['symbol'],
                record['option_type'],
                record['option_symbol'],
                record['expiration_date'],
                record['strike_price'],
                record['iv'],
                record['delta'],
                record['gamma'],
                record['open_interest'],
                record['volume'],
                record['gamma_exposure'],
                record['time_till_exp']
            )
            for record in options_records
        ]
        
        # Execute batch insert
        execute_values(cursor, insert_query, values)
        
        logger.info(f"Successfully loaded {len(options_records)} options records")
        return True
        
    except Exception as e:
        logger.error(f"Error loading options data: {str(e)}")
        return False
        
    finally:
        # Close connection
        close_connection(connection, cursor)