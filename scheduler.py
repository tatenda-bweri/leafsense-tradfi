"""ETL scheduling script for options analytics platform"""

import time
import os
import sys
import argparse
import django
from django.conf import settings
from app.etl.run import etl_process
from app.utils.logging_utils import get_logger, setup_logging

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Initialize logging
logger = get_logger(__name__)

def run_etl_scheduler(interval_minutes=None):
    """
    Run the ETL process continuously at specified intervals
    
    Args:
        interval_minutes: Interval between ETL runs in minutes (defaults to setting)
    """
    if interval_minutes is None:
        interval_minutes = getattr(settings, 'ETL_INTERVAL_MINUTES', 15)
    
    logger.info(f"Starting ETL scheduler with {interval_minutes} minute interval")
    
    while True:
        start_time = time.time()
        
        # Run ETL process
        success = etl_process()
        
        # Calculate elapsed time and sleep duration
        elapsed = time.time() - start_time
        sleep_time = max(0, interval_minutes * 60 - elapsed)
        
        if success:
            logger.info(f"ETL completed in {elapsed:.2f} seconds. Sleeping for {sleep_time:.2f} seconds")
        else:
            logger.warning(f"ETL failed. Retrying in {sleep_time:.2f} seconds")
        
        time.sleep(sleep_time)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="LeafSense ETL Scheduler for Options Analytics Platform"
    )
    parser.add_argument(
        "--interval", 
        "-i", 
        type=int,
        default=None,
        help="Interval between ETL runs in minutes (overrides settings.ETL_INTERVAL_MINUTES)"
    )
    parser.add_argument(
        "--once",
        "-o",
        action="store_true",
        help="Run ETL process once and exit"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()

def main():
    """Main entry point for the scheduler"""
    try:
        # Set up logging
        setup_logging()
        
        # Parse command line arguments
        args = parse_args()
        
        # Configure logging level
        if args.verbose:
            logger.setLevel('DEBUG')
            logger.debug("Verbose logging enabled")
        
        # Run ETL once or continuously
        if args.once:
            logger.info("Running ETL process once")
            success = etl_process()
            
            if success:
                logger.info("ETL process completed successfully")
                return 0
            else:
                logger.error("ETL process failed")
                return 1
        else:
            # Run scheduler with specified interval
            run_etl_scheduler(args.interval)
    
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user. Shutting down...")
        return 0
    except Exception as e:
        logger.critical(f"Unhandled exception in scheduler: {str(e)}")
        logger.exception("Exception details:")
        return 1

if __name__ == "__main__":
    sys.exit(main())