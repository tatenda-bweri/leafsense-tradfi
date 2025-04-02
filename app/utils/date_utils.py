"""Date handling utilities for options analytics"""

from datetime import datetime, timedelta
from pytz import timezone
import exchange_calendars as xcals
import numpy as np
import pandas as pd
from calendar import monthrange

def find_monthly_expiration(date, tz):
    """
    Identifies the third Friday of the month or Thursday if Friday is a holiday
    
    Args:
        date: Date to find monthly expiration for
        tz: Timezone
        
    Returns:
        Tuple of (expiration_date, trading_days)
    """
    # Get first day of the month
    first_day = datetime(date.year, date.month, 1, tzinfo=timezone(tz))
    
    # Get number of days in the month
    _, last_day_num = monthrange(date.year, date.month)
    last_day = datetime(date.year, date.month, last_day_num, tzinfo=timezone(tz))
    
    # Find all Fridays in the month
    all_days = pd.date_range(start=first_day, end=last_day)
    fridays = [day for day in all_days if day.weekday() == 4]  # 4 = Friday
    
    # Get the third Friday
    if len(fridays) >= 3:
        third_friday = fridays[2]
    else:
        # Fallback if not enough Fridays in the month
        third_friday = fridays[-1]
    
    # Check if the third Friday is a holiday (using US calendar)
    us_calendar = xcals.get_calendar("XNYS")  # NYSE calendar
    
    if not us_calendar.is_session(third_friday.strftime("%Y-%m-%d")):
        # If the third Friday is a holiday, use the previous trading day
        prev_trading_day = us_calendar.previous_session(third_friday.strftime("%Y-%m-%d"))
        expiration_date = pd.Timestamp(prev_trading_day).to_pydatetime().replace(tzinfo=timezone(tz))
    else:
        expiration_date = third_friday
    
    # Calculate trading days between current date and expiration
    if date <= expiration_date:
        trading_days = us_calendar.sessions_in_range(
            date.strftime("%Y-%m-%d"), 
            expiration_date.strftime("%Y-%m-%d")
        ).size
    else:
        # If the date is past expiration, return 0 trading days
        trading_days = 0
    
    return expiration_date, trading_days

def get_business_days_count(start_date, end_date):
    """
    Calculate number of business days between two dates
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        Number of business days
    """
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    
    # Ensure start_date <= end_date
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    
    # Use exchange_calendars to get accurate trading days
    us_calendar = xcals.get_calendar("XNYS")  # NYSE calendar
    
    # Convert datetime to string format required by exchange_calendars
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Get business days count
    try:
        trading_days = us_calendar.sessions_in_range(start_str, end_str).size
        return trading_days
    except Exception:
        # Fallback to numpy business days calculation
        business_days = np.busday_count(
            np.datetime64(start_date.date()),
            np.datetime64(end_date.date())
        )
        return business_days

def format_expiry_dates(options_df, tzinfo):
    """
    Format expiration dates in options dataframe
    
    Args:
        options_df: DataFrame with options data
        tzinfo: Timezone info
        
    Returns:
        DataFrame with formatted expiration dates
    """
    # Make a copy to avoid modifying the original
    df = options_df.copy()
    
    if df.empty or 'expiration_date' not in df.columns:
        return df
    
    # Ensure expiration dates are datetime objects with proper timezone
    if not pd.api.types.is_datetime64_any_dtype(df['expiration_date']):
        # Parse string dates to datetime objects
        df['expiration_date'] = pd.to_datetime(df['expiration_date'], errors='coerce')
    
    # Make timezone aware if not already
    if df['expiration_date'].dt.tz is None:
        df['expiration_date'] = df['expiration_date'].dt.tz_localize(tzinfo)
    elif df['expiration_date'].dt.tz != tzinfo:
        df['expiration_date'] = df['expiration_date'].dt.tz_convert(tzinfo)
    
    # Add additional date-related columns useful for analysis
    today = datetime.now(tzinfo)
    
    # Days till expiration
    df['days_till_expiry'] = (df['expiration_date'] - today).dt.total_seconds() / (24 * 60 * 60)
    
    # Business days till expiration
    df['business_days_till_expiry'] = df.apply(
        lambda row: get_business_days_count(today, row['expiration_date']),
        axis=1
    )
    
    # Add expiry type classification
    df['expiry_type'] = 'Other'
    
    # Classify expirations
    # 0DTE (0 days to expiry)
    df.loc[df['days_till_expiry'] < 1, 'expiry_type'] = '0DTE'
    
    # Weekly (1-5 business days)
    df.loc[(df['days_till_expiry'] >= 1) & (df['business_days_till_expiry'] <= 5), 'expiry_type'] = 'Weekly'
    
    # Monthly (identify third Friday)
    current_month = today.replace(day=1)
    next_month = (current_month + timedelta(days=32)).replace(day=1)
    
    # Get current month expiration
    current_month_exp, _ = find_monthly_expiration(current_month, tzinfo.zone)
    next_month_exp, _ = find_monthly_expiration(next_month, tzinfo.zone)
    
    # Mark monthly expirations
    df.loc[df['expiration_date'].dt.date == current_month_exp.date(), 'expiry_type'] = 'Monthly'
    df.loc[df['expiration_date'].dt.date == next_month_exp.date(), 'expiry_type'] = 'Monthly'
    
    return df

def trading_days_between(date1, date2, calendar_name="XNYS"):
    """
    Calculate trading days between two dates using exchange calendars
    
    Args:
        date1: First date
        date2: Second date
        calendar_name: Exchange calendar name (default: NYSE)
        
    Returns:
        Number of trading days between the dates
    """
    # Convert dates to string format
    if isinstance(date1, datetime):
        date1_str = date1.strftime("%Y-%m-%d")
    else:
        date1_str = date1
        
    if isinstance(date2, datetime):
        date2_str = date2.strftime("%Y-%m-%d")
    else:
        date2_str = date2
    
    # Get the calendar
    calendar = xcals.get_calendar(calendar_name)
    
    # Ensure date1 <= date2
    if date1_str > date2_str:
        date1_str, date2_str = date2_str, date1_str
    
    # Get trading days between the dates
    trading_days = calendar.sessions_in_range(date1_str, date2_str)
    return len(trading_days)

def is_third_friday(date):
    """
    Check if a date is the third Friday of its month
    
    Args:
        date: Date to check
        
    Returns:
        Boolean indicating if the date is the third Friday
    """
    if isinstance(date, str):
        date = datetime.fromisoformat(date.replace('Z', '+00:00'))
    
    # Check if it's a Friday
    if date.weekday() != 4:  # 4 = Friday
        return False
    
    # Check if it's the third Friday
    day_of_month = date.day
    return 15 <= day_of_month <= 21