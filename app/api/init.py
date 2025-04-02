"""API package initialization for LeafSense options analytics platform"""

from app.api.routes import api_urls

# Export the API URLs for use in the main URLconf
urls = api_urls()

# Define what's publicly available when importing from this package
__all__ = ['urls']