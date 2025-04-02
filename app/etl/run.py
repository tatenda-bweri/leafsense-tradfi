"""Main ETL runner for options analytics platform"""

from app.etl.fetch import fetch_spx_options_data, fetch_market_data
from app.etl.process import process_options_data, filter_options_by_range
from app.etl.load import transform_options_data, load_market_metrics, load_options_data
from app.utils.logging_utils import get_logger
import traceback
from django.conf import settings

logger = get_logger(__name__)

def extract_data():
    """
    Extract data from the API sources
    
    Returns:
        Tuple of (filtered_data, market_metrics, timestamp)
    """
    try:
        logger.info("Starting data extraction process")
        
        # Fetch options data from API
        json_data = fetch_spx_options_data()
        
        # Extract market metrics
        market_data = fetch_market_data()
        
        # Process options data
        options_df, timestamp = process_options_data(json_data)
        
        # Get spot price for filtering
        spot_price = market_data['spot_price']
        
        if spot_price > 0 and not options_df.empty:
            # Filter to relevant strike price range (default ±10%)
            range_percent = getattr(settings, 'OPTIONS_FILTER_RANGE', 0.10)
            filtered_df = filter_options_by_range(options_df, spot_price, range_percent)
        else:
            filtered_df = options_df
            
        logger.info(f"Data extraction complete: {len(filtered_df)} options contracts extracted")
        return (filtered_df, market_data, timestamp)
    
    except Exception as e:
        logger.error(f"Error in extract_data: {str(e)}")
        logger.error(traceback.format_exc())
        raise Exception(f"Data extraction failed: {str(e)}")

def etl_process():
    """
    Execute the full ETL process
    
    Returns:
        Boolean indicating success/failure
    """
    try:
        logger.info("Starting ETL process")
        
        # Extract data
        filtered_data, market_metrics, timestamp = extract_data()
        
        if filtered_data.empty:
            logger.warning("No options data to process. ETL process terminated.")
            return False
        
        # Transform options data for database
        options_records = transform_options_data(filtered_data, timestamp)
        
        if not options_records:
            logger.warning("No options records after transformation. ETL process terminated.")
            return False
        
        # Load market metrics into database
        market_metrics_success = load_market_metrics(market_metrics, timestamp)
        
        if not market_metrics_success:
            logger.error("Failed to load market metrics")
            return False
        
        # Load options data into database
        options_success = load_options_data(options_records)
        
        if not options_success:
            logger.error("Failed to load options data")
            return False
            
        logger.info(f"ETL process completed successfully: {len(options_records)} options records processed")
        return True
        
    except Exception as e:
        logger.error(f"ETL process failed: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def run_etl():
    """
    Run ETL process with proper exception handling
    for use in external scripts
    
    Returns:
        Boolean indicating success/failure
    """
    try:
        return etl_process()
    except Exception as e:
        logger.critical(f"Unhandled exception in ETL process: {str(e)}")
        logger.critical(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Allow direct execution for manual ETL runs
    import os
    import django
    
    # Setup Django environment if not already done
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    # Run ETL process
    success = run_etl()
    
    if success:
        print("ETL process completed successfully.")
    else:
        print("ETL process failed. Check logs for details.")
        exit(1)