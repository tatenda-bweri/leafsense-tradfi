"""Django models for options data"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import Sum, Avg, F, Q, Max
from django.utils import timezone
from datetime import timedelta
import json

class OptionsData(models.Model):
    """
    Model for options data with TimescaleDB hypertable
    """
    timestamp = models.DateTimeField()
    symbol = models.CharField(max_length=10)
    option_type = models.CharField(max_length=4)  # 'CALL' or 'PUT'
    option_symbol = models.CharField(max_length=50)
    expiration_date = models.DateTimeField()
    strike_price = models.DecimalField(max_digits=10, decimal_places=2)
    iv = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    delta = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    gamma = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    open_interest = models.IntegerField(null=True)
    volume = models.IntegerField(null=True)
    gamma_exposure = models.DecimalField(max_digits=18, decimal_places=6, null=True)
    time_till_exp = models.DecimalField(max_digits=10, decimal_places=6)
    
    class Meta:
        unique_together = ('timestamp', 'option_symbol')
        indexes = [
            models.Index(fields=['symbol', 'timestamp']),
            models.Index(fields=['expiration_date']),
            models.Index(fields=['strike_price']),
            models.Index(fields=['option_type']),
        ]
        verbose_name = 'Options Data'
        verbose_name_plural = 'Options Data'
        
    def __str__(self):
        return f"{self.option_symbol} @ {self.timestamp}"
    
    def to_dict(self):
        """
        Convert model instance to dictionary for API responses
        
        Returns:
            Dictionary representation of options data
        """
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'option_type': self.option_type,
            'option_symbol': self.option_symbol,
            'expiration_date': self.expiration_date.isoformat(),
            'strike_price': float(self.strike_price),
            'iv': float(self.iv) if self.iv else None,
            'delta': float(self.delta) if self.delta else None,
            'gamma': float(self.gamma) if self.gamma else None,
            'open_interest': self.open_interest,
            'volume': self.volume,
            'gamma_exposure': float(self.gamma_exposure) if self.gamma_exposure else None,
            'time_till_exp': float(self.time_till_exp),
        }
    
    @classmethod
    def get_latest_timestamp(cls):
        """Get the latest timestamp in the options data"""
        return cls.objects.aggregate(latest=Max('timestamp'))['latest']
    
    @classmethod
    def get_gamma_exposure_by_strike(cls, timestamp=None, symbol="_SPX"):
        """
        Get gamma exposure grouped by strike price
        
        Args:
            timestamp: Optional specific timestamp
            symbol: Symbol to filter by
            
        Returns:
            List of dictionaries with strike price and gamma exposure data
        """
        from django.db import connection
        
        # Get latest timestamp if not provided
        if timestamp is None:
            timestamp = cls.get_latest_timestamp()
            
        # Use raw SQL for better performance with complex aggregations
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH latest_data AS (
                    SELECT * FROM options_data
                    WHERE timestamp = %s AND symbol = %s
                )
                SELECT 
                    strike_price,
                    SUM(CASE WHEN option_type = 'CALL' THEN gamma_exposure ELSE 0 END) AS call_gamma_exposure,
                    SUM(CASE WHEN option_type = 'PUT' THEN gamma_exposure ELSE 0 END) AS put_gamma_exposure,
                    SUM(gamma_exposure) AS total_gamma_exposure,
                    MIN(expiration_date) AS earliest_expiry,
                    MAX(expiration_date) AS latest_expiry
                FROM latest_data
                GROUP BY strike_price
                ORDER BY strike_price
            """, [timestamp, symbol])
            
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Convert decimal and datetime objects to primitives
            for row in results:
                row['strike_price'] = float(row['strike_price'])
                row['call_gamma_exposure'] = float(row['call_gamma_exposure']) if row['call_gamma_exposure'] is not None else 0
                row['put_gamma_exposure'] = float(row['put_gamma_exposure']) if row['put_gamma_exposure'] is not None else 0
                row['total_gamma_exposure'] = float(row['total_gamma_exposure']) if row['total_gamma_exposure'] is not None else 0
                row['earliest_expiry'] = row['earliest_expiry'].isoformat() if row['earliest_expiry'] else None
                row['latest_expiry'] = row['latest_expiry'].isoformat() if row['latest_expiry'] else None
                
        return results
    
    @classmethod
    def get_gamma_by_expiry(cls, timestamp=None, symbol="_SPX", limit=10):
        """
        Get gamma exposure grouped by expiry date
        
        Args:
            timestamp: Optional specific timestamp
            symbol: Symbol to filter by
            limit: Number of records to return
            
        Returns:
            List of dictionaries with gamma by expiry
        """
        from django.db import connection
        
        # Get latest timestamp if not provided
        if timestamp is None:
            timestamp = cls.get_latest_timestamp()
            
        # Use raw SQL for better performance
        with connection.cursor() as cursor:
            cursor.execute("""
                WITH latest_data AS (
                    SELECT * FROM options_data
                    WHERE timestamp = %s AND symbol = %s
                )
                SELECT 
                    expiration_date,
                    SUM(CASE WHEN option_type = 'CALL' THEN gamma_exposure ELSE 0 END) AS call_gamma_exposure,
                    SUM(CASE WHEN option_type = 'PUT' THEN gamma_exposure ELSE 0 END) AS put_gamma_exposure,
                    SUM(gamma_exposure) AS total_gamma_exposure,
                    SUM(CASE WHEN option_type = 'CALL' THEN open_interest ELSE 0 END) AS call_open_interest,
                    SUM(CASE WHEN option_type = 'PUT' THEN open_interest ELSE 0 END) AS put_open_interest
                FROM latest_data
                GROUP BY expiration_date
                ORDER BY expiration_date
                LIMIT %s
            """, [timestamp, symbol, limit])
            
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Convert decimal and datetime objects to primitives
            for row in results:
                row['expiration_date'] = row['expiration_date'].isoformat()
                row['call_gamma_exposure'] = float(row['call_gamma_exposure']) if row['call_gamma_exposure'] is not None else 0
                row['put_gamma_exposure'] = float(row['put_gamma_exposure']) if row['put_gamma_exposure'] is not None else 0
                row['total_gamma_exposure'] = float(row['total_gamma_exposure']) if row['total_gamma_exposure'] is not None else 0
                
        return results
    
    @classmethod
    def get_highest_gamma_strikes(cls, timestamp=None, symbol="_SPX", limit=10):
        """
        Get strikes with highest absolute gamma exposure
        
        Args:
            timestamp: Optional specific timestamp
            symbol: Symbol to filter by
            limit: Number of records to return
            
        Returns:
            List of dictionaries with highest gamma strikes
        """
        # Get latest timestamp if not provided
        if timestamp is None:
            timestamp = cls.get_latest_timestamp()
            
        # Use Django ORM for this query
        from django.db.models import Func, F
        
        # Get total gamma exposure by strike
        result = cls.objects.filter(
            timestamp=timestamp,
            symbol=symbol
        ).values(
            'strike_price'
        ).annotate(
            total_gamma=Sum('gamma_exposure'),
            abs_gamma=Func(F('total_gamma'), function='ABS')
        ).order_by(
            '-abs_gamma'
        )[:limit]
        
        # Format the response
        data = []
        for row in result:
            data.append({
                'strike_price': float(row['strike_price']),
                'total_gamma_exposure': float(row['total_gamma']) if row['total_gamma'] else 0
            })
            
        return data
    
    @classmethod
    def get_options_chain(cls, expiry_date=None, timestamp=None, symbol="_SPX"):
        """
        Get options chain for a specific expiry date
        
        Args:
            expiry_date: Expiry date to filter by
            timestamp: Optional specific timestamp
            symbol: Symbol to filter by
            
        Returns:
            Dictionary with options chain data
        """
        # Get latest timestamp if not provided
        if timestamp is None:
            timestamp = cls.get_latest_timestamp()
            
        # If expiry_date not provided, get nearest expiry
        if expiry_date is None:
            expiry_date = cls.objects.filter(
                timestamp=timestamp,
                symbol=symbol,
                expiration_date__gte=timezone.now()
            ).order_by('expiration_date').values_list('expiration_date', flat=True).first()
        
        # Query for options data
        options = cls.objects.filter(
            timestamp=timestamp,
            symbol=symbol,
            expiration_date=expiry_date
        ).order_by('strike_price')
        
        # Format response
        calls = []
        puts = []
        
        for option in options:
            option_dict = option.to_dict()
            if option.option_type == 'CALL':
                calls.append(option_dict)
            else:
                puts.append(option_dict)
                
        return {
            'timestamp': timestamp.isoformat() if timestamp else None,
            'expiry_date': expiry_date.isoformat() if expiry_date else None,
            'symbol': symbol,
            'calls': calls,
            'puts': puts
        }