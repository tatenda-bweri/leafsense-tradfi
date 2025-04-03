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
        spot_price = json_data.get('data', {}).get('option', {}).get('current_price')
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
        data: Raw options data (list of dictionaries)
        today_ddt: Current date/time
        tzinfo: Timezone info
        
    Returns:
        DataFrame with formatted options data
    """
    try:
        keys_to_keep = ["option", "iv", "open_interest", "volume", "delta", "gamma", "strike_price"]
        df = pd.DataFrame([{k: d[k] for k in keys_to_keep if k in d} for d in data])
        formatted_df = pd.concat(
            [
                df.rename(
                    columns={
                        "option": "calls",
                        "iv": "call_iv",
                        "open_interest": "call_open_int",
                        "delta": "call_delta",
                        "gamma": "call_gamma",
                        "volume": "call_volume",
                    }
                ).iloc[0::2].reset_index(drop=True),
                df.rename(
                    columns={
                        "option": "puts",
                        "iv": "put_iv",
                        "open_interest": "put_open_int",
                        "delta": "put_delta",
                        "gamma": "put_gamma",
                        "volume": "put_volume",
                    }
                ).iloc[1::2].reset_index(drop=True),
            ],
            axis=1,
        )
        # Extract strike price from calls column using a regex
        formatted_df["strike_price"] = (
            formatted_df["calls"].str.extract(r"\d[A-Z](\d+)\d\d\d").astype(float)
        )
        # Extract expiration date from calls column
        formatted_df["expiration_date"] = formatted_df["calls"].str.extract(r"[A-Z](\d+)")
        formatted_df["expiration_date"] = pd.to_datetime(
            formatted_df["expiration_date"], format="%y%m%d"
        ).dt.tz_localize(tzinfo) + timedelta(hours=16)
    
        # Calculate business day counts and time till expiration in years
        busday_counts = np.busday_count(
            today_ddt.date(), formatted_df["expiration_date"].values.astype("datetime64[D]")
        )
        formatted_df["time_till_exp"] = np.where(busday_counts == 0, 1/252, busday_counts/252)
    
        formatted_df = formatted_df.sort_values(by=["expiration_date", "strike_price"]).reset_index(drop=True)
        logger.info(f"Formatted {len(formatted_df)} options rows")
        return formatted_df

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