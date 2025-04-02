"""Django models for market metrics data"""

from django.db import models
from django.utils import timezone
from datetime import timedelta
import json

class MarketMetrics(models.Model):
    """
    Model for market metrics data with TimescaleDB hypertable
    """
    timestamp = models.DateTimeField()
    symbol = models.CharField(max_length=10)
    spot_price = models.DecimalField(max_digits=10, decimal_places=2)
    prev_day_close = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    price_change = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    price_change_pct = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    
    class Meta:
        unique_together = ('timestamp', 'symbol')
        indexes = [
            models.Index(fields=['symbol', '-timestamp']),
        ]
        verbose_name = 'Market Metric'
        verbose_name_plural = 'Market Metrics'
        
    def __str__(self):
        return f"{self.symbol} @ {self.timestamp}"
    
    @classmethod
    def get_latest(cls, symbol="_SPX"):
        """Get the latest market metrics for a symbol"""
        return cls.objects.filter(symbol=symbol).order_by('-timestamp').first()
    
    @classmethod
    def get_historical(cls, symbol="_SPX", days=7):
        """
        Get historical market metrics for the specified days
        
        Args:
            symbol: Market symbol to query
            days: Number of days to look back
            
        Returns:
            QuerySet of MarketMetrics objects
        """
        start_date = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            symbol=symbol,
            timestamp__gte=start_date
        ).order_by('timestamp')
    
    @classmethod
    def get_daily_summary(cls, symbol="_SPX", days=30):
        """
        Get daily summary of market metrics
        
        Args:
            symbol: Market symbol to query
            days: Number of days to look back
            
        Returns:
            List of daily metrics
        """
        # Use raw SQL for better performance with TimescaleDB
        from django.db import connection
        
        start_date = (timezone.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    date_trunc('day', timestamp) AS day,
                    AVG(spot_price) AS avg_price,
                    MAX(spot_price) AS high_price,
                    MIN(spot_price) AS low_price,
                    FIRST_VALUE(spot_price) OVER (PARTITION BY date_trunc('day', timestamp) ORDER BY timestamp) AS open_price,
                    LAST_VALUE(spot_price) OVER (PARTITION BY date_trunc('day', timestamp) ORDER BY timestamp) AS close_price
                FROM 
                    market_metrics
                WHERE 
                    symbol = %s AND timestamp >= %s
                GROUP BY 
                    day, timestamp
                ORDER BY 
                    day
            """, [symbol, start_date])
            
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        return results
    
    def to_dict(self):
        """
        Convert model instance to dictionary for API responses
        
        Returns:
            Dictionary representation of market metrics
        """
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'spot_price': float(self.spot_price),
            'prev_day_close': float(self.prev_day_close) if self.prev_day_close else None,
            'price_change': float(self.price_change) if self.price_change else None,
            'price_change_pct': float(self.price_change_pct) if self.price_change_pct else None,
        }
    
    def calculate_changes(self):
        """
        Calculate price changes if not already set
        
        Returns:
            Self instance with updated values
        """
        if self.prev_day_close and self.prev_day_close > 0:
            if not self.price_change:
                self.price_change = self.spot_price - self.prev_day_close
            
            if not self.price_change_pct:
                self.price_change_pct = (self.price_change / self.prev_day_close) * 100
                
        return self
    
    def save(self, *args, **kwargs):
        """Override save to calculate changes if needed"""
        self.calculate_changes()
        super().save(*args, **kwargs)