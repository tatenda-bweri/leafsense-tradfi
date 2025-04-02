"""Data processing and transformation functions for options data"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateparser.date import DateDataParser
from pytz import timezone
import exchange_calendars as xcals
from calendar import monthrange
from app.utils.date_utils import find_monthly_expiration
from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

def process_options_data(json_data, tz="America/New_York"):
    """
    Process raw options data from JSON to structured format
    
    Args:
        json_data: Raw JSON data from API
        tz: Timezone for data processing
        
    Returns:
        Tuple of (processed_data_df, timestamp)
    """
    try:
        # Parse timestamp to get current date
        tzinfo = timezone(tz)
        timestamp_str = json_data.get('data', {}).get('timestamp')
        
        if timestamp_str:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')).astimezone(tzinfo)
        else:
            timestamp = datetime.now(tzinfo)
        
        logger.info(f"Processing options data for timestamp: {timestamp}")
        
        # Extract options data from JSON
        options_data = json_data.get('data', {}).get('options', [])
        
        if not options_data:
            logger.warning("No options data found in JSON response")
            return pd.DataFrame(), timestamp
        
        # Format options data into DataFrame
        options_df = format_options_data(options_data, timestamp, tzinfo)
        
        # Filter expired options
        options_df = options_df[options_df['expiration_date'] > timestamp]
        
        # Calculate spot price from data if available
        spot_price = json_data.get('data', {}).get('option', {}).get('close')
        if spot_price:
            spot_price = float(spot_price)
            
            # Calculate gamma exposure
            options_df = calculate_gamma_exposure(options_df, spot_price)
        
        logger.info(f"Processed {len(options_df)} options contracts")
        return options_df, timestamp
    
    except Exception as e:
        logger.error(f"Error processing options data: {str(e)}")
        raise Exception(f"Failed to process options data: {str(e)}")

def format_options_data(data, today_ddt, tzinfo):
    """
    Format raw options data into usable DataFrame structure
    
    Args:
        data: Raw options data
        today_ddt: Current date/time
        tzinfo: Timezone info
        
    Returns:
        DataFrame with formatted options data
    """
    try:
        # Convert to DataFrame if list
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = pd.DataFrame([data])
        
        # Create empty DataFrame if no data
        if df.empty:
            logger.warning("No data to format")
            return pd.DataFrame()
        
        # Extract option details from each option
        option_rows = []
        
        for _, row in df.iterrows():
            # Get strikes data
            strikes = row.get('strikes', [])
            
            if not strikes:
                continue
                
            for strike in strikes:
                strike_price = float(strike.get('strike', 0))
                
                # Process call data
                call_data = strike.get('call', {})
                put_data = strike.get('put', {})
                
                # Extract expiration date
                expiry_str = strike.get('expiry')
                if not expiry_str:
                    continue
                
                # Parse expiry date
                parser = DateDataParser()
                expiry_date = parser.get_date_data(expiry_str).date_obj
                
                if not expiry_date:
                    continue
                
                # Make timezone aware
                expiry_date = expiry_date.replace(tzinfo=tzinfo)
                
                # Calculate time till expiration in years
                time_till_exp = (expiry_date - today_ddt).total_seconds() / (365.25 * 24 * 60 * 60)
                
                # Create option record
                option_row = {
                    'expiration_date': expiry_date,
                    'strike_price': strike_price,
                    'time_till_exp': time_till_exp,
                    
                    # Call data
                    'call_option_symbol': call_data.get('option_root', '') + call_data.get('option_ext', ''),
                    'call_iv': float(call_data.get('iv', 0) or 0),
                    'call_delta': float(call_data.get('delta', 0) or 0),
                    'call_gamma': float(call_data.get('gamma', 0) or 0),
                    'call_open_interest': int(call_data.get('open_interest', 0) or 0),
                    'call_volume': int(call_data.get('volume', 0) or 0),
                    
                    # Put data
                    'put_option_symbol': put_data.get('option_root', '') + put_data.get('option_ext', ''),
                    'put_iv': float(put_data.get('iv', 0) or 0),
                    'put_delta': float(put_data.get('delta', 0) or 0),
                    'put_gamma': float(put_data.get('gamma', 0) or 0),
                    'put_open_interest': int(put_data.get('open_interest', 0) or 0),
                    'put_volume': int(put_data.get('volume', 0) or 0),
                }
                
                option_rows.append(option_row)
        
        # Create DataFrame from rows
        options_df = pd.DataFrame(option_rows)
        
        # Sort by expiration date and strike price
        if not options_df.empty:
            options_df = options_df.sort_values(['expiration_date', 'strike_price'])
            
        logger.info(f"Formatted {len(options_df)} options rows")
        return options_df
        
    except Exception as e:
        logger.error(f"Error formatting options data: {str(e)}")
        raise Exception(f"Failed to format options data: {str(e)}")

def calculate_gamma_exposure(option_data, spot_price):
    """
    Calculate gamma exposure for options based on open interest and spot price
    
    Args:
        option_data: DataFrame with options data
        spot_price: Current spot price
        
    Returns:
        DataFrame with gamma exposure calculations
    """
    try:
        # Make a copy to avoid modifying the original
        df = option_data.copy()
        
        # Skip calculation if DataFrame is empty
        if df.empty:
            return df
            
        # Calculate contract multiplier (SPX is typically 100)
        contract_multiplier = 100
        
        # Gamma exposure is gamma * open_interest * contract_multiplier * (spot_price^2 / 100)
        # The division by 100 is to scale the exposure to a more manageable number
        
        # Calculate gamma exposure for calls (positive gamma)
        df['call_gamma_exposure'] = df['call_gamma'] * df['call_open_interest'] * \
                                   contract_multiplier * (spot_price ** 2 / 100)
        
        # Calculate gamma exposure for puts (negative gamma for dealers with long put positions)
        df['put_gamma_exposure'] = -1 * df['put_gamma'] * df['put_open_interest'] * \
                                  contract_multiplier * (spot_price ** 2 / 100)
        
        # Calculate total gamma exposure per strike
        df['total_gamma_exposure'] = (df['call_gamma_exposure'] + df['put_gamma_exposure']) / 1e9
        df['total_gamma_exposure'] = df['total_gamma_exposure'].round(2)  # Round to 2 decimal places
        
        logger.info(f"Calculated gamma exposure with spot price {spot_price}")
        return df
        
    except Exception as e:
        logger.error(f"Error calculating gamma exposure: {str(e)}")
        raise Exception(f"Failed to calculate gamma exposure: {str(e)}")

def filter_options_by_range(options_df, spot_price, range_percent=0.10):
    """
    Filter options to those within a specific range from spot price
    
    Args:
        options_df: DataFrame with options data
        spot_price: Current spot price
        range_percent: Percentage range to filter (e.g., 0.10 = ±10%)
        
    Returns:
        Filtered DataFrame
    """
    try:
        # Calculate strike range
        lower_bound = spot_price * (1 - range_percent)
        upper_bound = spot_price * (1 + range_percent)
        
        # Filter by strike price
        filtered_df = options_df[(options_df['strike_price'] >= lower_bound) & 
                                (options_df['strike_price'] <= upper_bound)]
        
        logger.info(f"Filtered options to strikes between {lower_bound:.2f} and {upper_bound:.2f}")
        logger.info(f"Retained {len(filtered_df)} out of {len(options_df)} options")
        
        return filtered_df
        
    except Exception as e:
        logger.error(f"Error filtering options by range: {str(e)}")
        return options_df  # Return original on error