"""Business logic for market metrics"""

from app.models.market import MarketMetrics
from django.db.models import Max
from django.utils import timezone
from datetime import timedelta

class MetricsService:
    """Service for interacting with market metrics data"""
    
    def get_latest_metrics(self, symbol="_SPX"):
        """
        Get latest market metrics for a symbol
        
        Args:
            symbol: Symbol to get metrics for
            
        Returns:
            Dictionary with market metrics
        """
        # Get the latest metrics from DB for the symbol
        metrics = MarketMetrics.get_latest(symbol=symbol)
        
        if metrics:
            # Convert to dictionary format
            return metrics.to_dict()
        else:
            # Return empty metrics if no data found
            return {
                'timestamp': timezone.now().isoformat(),
                'symbol': symbol,
                'spot_price': 0,
                'prev_day_close': 0,
                'price_change': 0,
                'price_change_pct': 0,
                'status': 'No data available'
            }
    
    def get_historical_metrics(self, symbol="_SPX", days=7):
        """
        Get historical metrics for a symbol
        
        Args:
            symbol: Symbol to get metrics for
            days: Number of days of history
            
        Returns:
            List of dictionaries with historical metrics
        """
        # Query database for historical data
        metrics_queryset = MarketMetrics.get_historical(symbol=symbol, days=days)
        
        # Format into list of dictionaries
        metrics_list = [metric.to_dict() for metric in metrics_queryset]
        
        # If daily summary data is requested and we have enough data
        if days >= 5:
            # Get daily OHLC data for better chart representation
            daily_data = MarketMetrics.get_daily_summary(symbol=symbol, days=days)
            if daily_data:
                # Add daily summary data under a separate key
                return {
                    'time_series': metrics_list,
                    'daily_summary': daily_data
                }
        
        return metrics_list
    
    def get_price_change_metrics(self, symbol="_SPX"):
        """
        Get price change metrics with additional calculations
        
        Args:
            symbol: Symbol to get metrics for
            
        Returns:
            Dictionary with enhanced price change metrics
        """
        # Get the latest metrics
        metrics = self.get_latest_metrics(symbol=symbol)
        
        # Calculate additional metrics
        if metrics.get('spot_price') and metrics.get('prev_day_close'):
            spot = float(metrics['spot_price'])
            prev = float(metrics['prev_day_close'])
            
            # Add 1-day metrics (already in base metrics)
            metrics['1d_change'] = metrics['price_change']
            metrics['1d_change_pct'] = metrics['price_change_pct']
            
            # Get weekly data for 5-day change
            week_ago = timezone.now() - timedelta(days=7)
            week_metrics = MarketMetrics.objects.filter(
                symbol=symbol,
                timestamp__gte=week_ago
            ).order_by('timestamp').first()
            
            if week_metrics:
                week_price = float(week_metrics.spot_price)
                metrics['5d_change'] = spot - week_price
                metrics['5d_change_pct'] = (metrics['5d_change'] / week_price * 100) if week_price else 0
            
            # Get monthly data for 30-day change
            month_ago = timezone.now() - timedelta(days=30)
            month_metrics = MarketMetrics.objects.filter(
                symbol=symbol,
                timestamp__gte=month_ago
            ).order_by('timestamp').first()
            
            if month_metrics:
                month_price = float(month_metrics.spot_price)
                metrics['30d_change'] = spot - month_price
                metrics['30d_change_pct'] = (metrics['30d_change'] / month_price * 100) if month_price else 0
                
            # Calculate volatility (standard deviation of daily returns)
            try:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT STDDEV(price_change_pct) AS daily_volatility
                        FROM market_metrics
                        WHERE symbol = %s
                        AND timestamp >= %s
                    """, [symbol, timezone.now() - timedelta(days=30)])
                    
                    result = cursor.fetchone()
                    if result and result[0]:
                        metrics['30d_volatility'] = float(result[0])
                        # Annualized volatility (approximate using trading days)
                        metrics['annualized_volatility'] = float(result[0]) * (252 ** 0.5)
            except Exception:
                # Volatility calculation is optional
                pass
        
        return metrics
    
    def get_metrics_summary(self, symbol="_SPX"):
        """
        Get a comprehensive summary of market metrics
        
        Args:
            symbol: Symbol to get metrics for
            
        Returns:
            Dictionary with comprehensive metrics
        """
        # Get enhanced price change metrics
        metrics = self.get_price_change_metrics(symbol)
        
        # Add any additional summary statistics needed for dashboards
        # This could include moving averages, support/resistance levels, etc.
        
        return metrics