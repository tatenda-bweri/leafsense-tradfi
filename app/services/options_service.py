"""Business logic for options data"""

import pandas as pd
from app.models.options import OptionsData
from django.db import connection
from django.db.models import Sum, Case, When, F, Value, DecimalField, Func
from django.utils import timezone
from datetime import datetime, timedelta

class OptionsService:
    """Service for interacting with options data"""
    
    def get_options_data(self, timestamp=None, expiry_filter=None):
        """
        Get options data with optional filters
        
        Args:
            timestamp: Optional specific timestamp
            expiry_filter: Optional expiry date filter
            
        Returns:
            Dictionary with options data
        """
        # Get the latest timestamp if not specified
        if timestamp is None:
            timestamp = OptionsData.get_latest_timestamp()
        elif isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
        # Base query
        query = OptionsData.objects.filter(timestamp=timestamp)
        
        # Apply expiry filter if provided
        if expiry_filter:
            today = timezone.now().date()
            
            if expiry_filter == '0DTE':
                # Same day expiration
                query = query.filter(expiration_date__date=today)
            elif expiry_filter == 'weekly':
                # Weekly expiration (within next 7 days)
                next_week = today + timedelta(days=7)
                query = query.filter(
                    expiration_date__date__gte=today,
                    expiration_date__date__lte=next_week
                )
            elif expiry_filter == 'monthly':
                # Monthly expiration (closest monthly expiry - typically 3rd Friday)
                # For simplicity, let's consider options expiring this month
                next_month = today.replace(day=1, month=today.month+1 if today.month < 12 else 1,
                                          year=today.year if today.month < 12 else today.year+1)
                query = query.filter(
                    expiration_date__date__gte=today,
                    expiration_date__date__lt=next_month
                )
        
        # Execute query efficiently
        options = query.order_by('strike_price', 'option_type')
        
        # Format results
        options_data = []
        for opt in options:
            options_data.append(opt.to_dict())
        
        # Group options by expiry date
        expiry_dates = sorted(set(opt['expiration_date'] for opt in options_data))
        
        # Structure the response
        result = {
            "timestamp": timestamp.isoformat() if timestamp else None,
            "expiry_dates": expiry_dates,
            "options_count": len(options_data),
            "options": options_data
        }
        
        return result
    
    def get_gamma_exposure_by_strike(self, timestamp=None):
        """
        Get gamma exposure data grouped by strike price
        
        Args:
            timestamp: Optional specific timestamp
            
        Returns:
            List of dictionaries with strike price and gamma exposure data
        """
        # Use the model's method for this query
        return OptionsData.get_gamma_exposure_by_strike(timestamp=timestamp)
    
    def get_highest_gamma_strikes(self, timestamp=None, limit=10):
        """
        Get strikes with highest gamma exposure
        
        Args:
            timestamp: Optional specific timestamp
            limit: Number of records to return
            
        Returns:
            List of dictionaries with highest gamma strikes
        """
        # Use the model's method for this query
        return OptionsData.get_highest_gamma_strikes(timestamp=timestamp, limit=limit)
    
    def get_gamma_by_expiry(self, timestamp=None, limit=10):
        """
        Get gamma exposure grouped by expiry date
        
        Args:
            timestamp: Optional specific timestamp
            limit: Number of records to return
            
        Returns:
            List of dictionaries with gamma by expiry
        """
        # Use the model's method for this query
        return OptionsData.get_gamma_by_expiry(timestamp=timestamp, limit=limit)
    
    def get_gamma_levels(self, timestamp=None):
        """
        Get key gamma levels for analysis
        
        Args:
            timestamp: Optional specific timestamp
            
        Returns:
            Dictionary with gamma levels data
        """
        # Get gamma exposure by strike
        gamma_exposure = self.get_gamma_exposure_by_strike(timestamp=timestamp)
        
        if not gamma_exposure:
            return {"error": "No gamma exposure data available"}
            
        # Sort by absolute gamma exposure
        gamma_exposure_sorted = sorted(
            gamma_exposure,
            key=lambda x: abs(x['total_gamma_exposure']),
            reverse=True
        )
        
        # Get top positive and negative gamma levels
        positive_levels = [item for item in gamma_exposure_sorted 
                          if item['total_gamma_exposure'] > 0][:5]
        negative_levels = [item for item in gamma_exposure_sorted 
                          if item['total_gamma_exposure'] < 0][:5]
        
        # Calculate cumulative gamma exposure
        cumulative_gamma = 0
        strikes = []
        
        for strike in sorted(gamma_exposure, key=lambda x: x['strike_price']):
            cumulative_gamma += strike['total_gamma_exposure']
            strikes.append({
                'strike_price': strike['strike_price'],
                'gamma_exposure': strike['total_gamma_exposure'],
                'cumulative_gamma': cumulative_gamma
            })
        
        # Calculate zero-gamma level (strike where cumulative gamma crosses zero)
        zero_gamma_level = None
        for i in range(1, len(strikes)):
            if (strikes[i-1]['cumulative_gamma'] <= 0 and strikes[i]['cumulative_gamma'] > 0) or \
               (strikes[i-1]['cumulative_gamma'] >= 0 and strikes[i]['cumulative_gamma'] < 0):
                # Linear interpolation to find zero crossing
                s1 = strikes[i-1]['strike_price']
                s2 = strikes[i]['strike_price']
                g1 = strikes[i-1]['cumulative_gamma']
                g2 = strikes[i]['cumulative_gamma']
                
                # Avoid division by zero
                if g1 != g2:
                    zero_gamma_level = s1 + (s2 - s1) * (-g1) / (g2 - g1)
                else:
                    zero_gamma_level = (s1 + s2) / 2
                break
        
        return {
            "top_positive_gamma_strikes": positive_levels,
            "top_negative_gamma_strikes": negative_levels,
            "zero_gamma_level": zero_gamma_level,
            "total_gamma_exposure": sum(s['total_gamma_exposure'] for s in gamma_exposure)
        }
    
    def get_options_chain(self, expiry_date=None, timestamp=None):
        """
        Get options chain for specific expiry date
        
        Args:
            expiry_date: Expiry date for options chain
            timestamp: Optional specific timestamp
            
        Returns:
            Dictionary with options chain data
        """
        return OptionsData.get_options_chain(expiry_date=expiry_date, timestamp=timestamp)
    
    def get_gamma_exposure_summary(self, timestamp=None):
        """
        Get summary of gamma exposure across different time frames
        
        Args:
            timestamp: Optional specific timestamp
            
        Returns:
            Dictionary with gamma exposure summary
        """
        if timestamp is None:
            timestamp = OptionsData.get_latest_timestamp()
            
        # Get gamma by expiry with a higher limit to capture more data
        gamma_by_expiry = self.get_gamma_by_expiry(timestamp=timestamp, limit=20)
        
        # Calculate near-term gamma (options expiring within 7 days)
        today = timezone.now().date().isoformat() if isinstance(timestamp, datetime) else timestamp.split('T')[0]
        next_week = (timezone.now().date() + timedelta(days=7)).isoformat()
        
        near_term_gamma = sum(
            item['total_gamma_exposure'] 
            for item in gamma_by_expiry 
            if item['expiration_date'].split('T')[0] <= next_week
        )
        
        # Calculate mid-term gamma (options expiring within 30 days)
        next_month = (timezone.now().date() + timedelta(days=30)).isoformat()
        mid_term_gamma = sum(
            item['total_gamma_exposure'] 
            for item in gamma_by_expiry 
            if item['expiration_date'].split('T')[0] <= next_month
        ) - near_term_gamma
        
        # Calculate long-term gamma (options expiring after 30 days)
        long_term_gamma = sum(
            item['total_gamma_exposure'] 
            for item in gamma_by_expiry 
            if item['expiration_date'].split('T')[0] > next_month
        )
        
        # Calculate total gamma
        total_gamma = near_term_gamma + mid_term_gamma + long_term_gamma
        
        # Calculate percentages
        total_abs = abs(near_term_gamma) + abs(mid_term_gamma) + abs(long_term_gamma)
        if total_abs > 0:
            near_term_pct = (abs(near_term_gamma) / total_abs) * 100
            mid_term_pct = (abs(mid_term_gamma) / total_abs) * 100
            long_term_pct = (abs(long_term_gamma) / total_abs) * 100
        else:
            near_term_pct = mid_term_pct = long_term_pct = 0
            
        return {
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "total_gamma": total_gamma,
            "near_term_gamma": {
                "value": near_term_gamma,
                "percentage": near_term_pct
            },
            "mid_term_gamma": {
                "value": mid_term_gamma,
                "percentage": mid_term_pct
            },
            "long_term_gamma": {
                "value": long_term_gamma,
                "percentage": long_term_pct
            },
            "expiry_breakdown": gamma_by_expiry
        }