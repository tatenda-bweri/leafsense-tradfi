"""API endpoints for options analytics platform"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from app.services.options_service import OptionsService
from app.services.metrics_service import MetricsService
from app.utils.logging_utils import get_logger
import json
from datetime import datetime, timedelta

logger = get_logger(__name__)
options_service = OptionsService()
metrics_service = MetricsService()

@require_http_methods(["GET"])
def market_metrics(request):
    """
    API endpoint to get the latest market metrics
    
    Returns:
        JSON response with market metrics
    """
    try:
        metrics = metrics_service.get_latest_metrics()
        return JsonResponse(metrics)
    except Exception as e:
        logger.error(f"Error fetching market metrics: {str(e)}")
        return JsonResponse({"error": "Failed to fetch market metrics"}, status=500)

@require_http_methods(["GET"])
def historical_metrics(request):
    """
    API endpoint to get historical market metrics
    
    Query params:
        days: Number of days of history to retrieve (default: 7)
    
    Returns:
        JSON response with historical metrics
    """
    try:
        days = int(request.GET.get('days', 7))
        metrics = metrics_service.get_historical_metrics(days=days)
        return JsonResponse({"data": metrics})
    except Exception as e:
        logger.error(f"Error fetching historical metrics: {str(e)}")
        return JsonResponse({"error": "Failed to fetch historical metrics"}, status=500)

@require_http_methods(["GET"])
def gamma_exposure(request):
    """
    API endpoint to get gamma exposure data by strike price
    
    Query params:
        expiry_filter: Filter by expiry date (All, 0DTE, Weekly, Monthly)
        timestamp: Optional specific timestamp
    
    Returns:
        JSON response with gamma exposure data
    """
    try:
        expiry_filter = request.GET.get('expiry_filter', 'All')
        timestamp = request.GET.get('timestamp', None)
        
        data = options_service.get_gamma_exposure_by_strike(timestamp=timestamp)
        
        # Apply expiry filter if needed
        if expiry_filter != 'All':
            # Convert filter to appropriate date range
            now = datetime.now()
            
            if expiry_filter == '0DTE':
                # Same day expiration
                end_date = now.replace(hour=23, minute=59, second=59)
                data = [item for item in data if item['expiration_date'] <= end_date.isoformat()]
            elif expiry_filter == 'Weekly':
                # Current week expiration
                end_date = now + timedelta(days=7-now.weekday())
                data = [item for item in data if item['expiration_date'] <= end_date.isoformat()]
            elif expiry_filter == 'Monthly':
                # Current month expiration
                end_date = now.replace(month=now.month+1 if now.month < 12 else 1, 
                                     year=now.year if now.month < 12 else now.year+1, 
                                     day=1) - timedelta(days=1)
                data = [item for item in data if item['expiration_date'] <= end_date.isoformat()]
        
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.error(f"Error fetching gamma exposure: {str(e)}")
        return JsonResponse({"error": "Failed to fetch gamma exposure data"}, status=500)

@require_http_methods(["GET"])
def gamma_by_expiry(request):
    """
    API endpoint to get gamma exposure grouped by expiry date
    
    Query params:
        limit: Number of records to return (default: 10)
        timestamp: Optional specific timestamp
    
    Returns:
        JSON response with gamma exposure by expiry
    """
    try:
        limit = int(request.GET.get('limit', 10))
        timestamp = request.GET.get('timestamp', None)
        
        data = options_service.get_gamma_by_expiry(timestamp=timestamp, limit=limit)
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.error(f"Error fetching gamma by expiry: {str(e)}")
        return JsonResponse({"error": "Failed to fetch gamma by expiry data"}, status=500)

@require_http_methods(["GET"])
def highest_gamma_strikes(request):
    """
    API endpoint to get strikes with highest gamma exposure
    
    Query params:
        limit: Number of records to return (default: 10)
        timestamp: Optional specific timestamp
    
    Returns:
        JSON response with highest gamma strikes
    """
    try:
        limit = int(request.GET.get('limit', 10))
        timestamp = request.GET.get('timestamp', None)
        
        data = options_service.get_highest_gamma_strikes(timestamp=timestamp, limit=limit)
        return JsonResponse(data, safe=False)
    except Exception as e:
        logger.error(f"Error fetching highest gamma strikes: {str(e)}")
        return JsonResponse({"error": "Failed to fetch highest gamma strikes data"}, status=500)

@require_http_methods(["GET"])
def options_data(request):
    """
    API endpoint to get raw options data
    
    Query params:
        expiry_filter: Filter by expiry date
        timestamp: Optional specific timestamp
        
    Returns:
        JSON response with options data
    """
    try:
        expiry_filter = request.GET.get('expiry_filter', None)
        timestamp = request.GET.get('timestamp', None)
        
        data = options_service.get_options_data(timestamp=timestamp, expiry_filter=expiry_filter)
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error fetching options data: {str(e)}")
        return JsonResponse({"error": "Failed to fetch options data"}, status=500)

def api_urls():
    """
    Define API URLs for inclusion in Django URLconf
    """
    from django.urls import path
    
    return [
        path('market-metrics/', market_metrics, name='market_metrics'),
        path('historical-metrics/', historical_metrics, name='historical_metrics'),
        path('gamma-exposure/', gamma_exposure, name='gamma_exposure'),
        path('gamma-by-expiry/', gamma_by_expiry, name='gamma_by_expiry'),
        path('highest-gamma-strikes/', highest_gamma_strikes, name='highest_gamma_strikes'),
        path('options-data/', options_data, name='options_data'),
    ]