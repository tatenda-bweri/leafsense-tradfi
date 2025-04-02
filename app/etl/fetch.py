"""Data fetching functions for options data ETL process"""

import requests
import logging
import time
from django.conf import settings
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

def fetch_spx_options_data(api_url=None):
    """
    Fetches SPX options data from CBOE API with retry logic
    
    Args:
        api_url: URL for CBOE options data API
        
    Returns:
        JSON response from API
        
    Raises:
        Exception if data fetch fails after retries
    """
    # Set default API URL if none provided
    if api_url is None:
        symbol = getattr(settings, 'API_DEFAULT_SYMBOL', '_SPX')
        base_url = getattr(settings, 'API_BASE_URL', 'https://cdn.cboe.com/api/global/delayed_quotes/options/')
        if not symbol.endswith('.json'):
            symbol += '.json'
        api_url = f"{base_url}{symbol}"
    
    # Implement retry logic (3 attempts)
    max_retries = 3
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching options data from {api_url} (attempt {attempt + 1}/{max_retries})")
            
            # Make the request with appropriate headers
            headers = {
                'User-Agent': 'LeafSense Options Analytics/1.0',
                'Accept': 'application/json'
            }
            
            response = requests.get(api_url, headers=headers, timeout=30)
            
            # Handle HTTP errors
            response.raise_for_status()
            
            # Parse JSON data
            data = response.json()
            
            logger.info(f"Successfully fetched options data: {len(data)} bytes")
            return data
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error(f"Failed to fetch options data after {max_retries} attempts")
                raise Exception(f"Failed to fetch options data: {str(e)}")
        
        except ValueError as e:
            logger.error(f"Invalid JSON response: {str(e)}")
            raise Exception(f"Invalid JSON response: {str(e)}")

def fetch_market_data():
    """
    Fetch additional market data from other sources if needed
    
    Returns:
        Dictionary with market data
    """
    try:
        # For now, we'll extract market data from the options API response
        # This could be expanded to fetch from additional sources as needed
        options_data = fetch_spx_options_data()
        
        # Extract market data from options response
        market_data = {
            'symbol': options_data.symbol,
            'spot_price': options_data["data.current_price"][0].astype(float),
            'prev_day_close': options_data["data.prev_day_close"][0].astype(float),
            'price_change': options_data["data.price_change"][0].astype(float),
            'price_change_pct': options_data["data.price_change_percent"][0].astype(float),
        }
        
        logger.info(f"Market data fetched successfully for {market_data['symbol']}")
        return market_data
        
    except Exception as e:
        logger.error(f"Error fetching market data: {str(e)}")
        # Return default values if fetch fails
        return {
            'symbol': '_SPX',
            'spot_price': 0,
            'prev_day_close': 0,
            'price_change': 0,
            'price_change_pct': 0
        }