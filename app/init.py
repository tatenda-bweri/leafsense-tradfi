"""Application package initialization for LeafSense options analytics platform"""

# Import key components from subpackages for easy access
from app.api import urls as api_urls
from app.database.schema import initialize_database
from app.etl.run import run_etl, etl_process
from app.utils.logging_utils import setup_logging, get_logger
from app.models import MarketMetrics, OptionsData
from app.services import MetricsService, OptionsService

# Initialize logging for the application
logger = get_logger(__name__)

# Define publicly available imports
__all__ = [
    # Core functionality
    'api_urls',
    'initialize_database',
    'run_etl',
    'etl_process',
    'setup_logging',
    
    # Models
    'MarketMetrics',
    'OptionsData',
    
    # Services
    'MetricsService',
    'OptionsService'
]

# Application metadata
__version__ = '1.0.0'
__author__ = 'LeafSense Team'
__description__ = 'Options analytics platform for gamma exposure analysis'

logger.info(f"LeafSense options analytics platform v{__version__} initialized")