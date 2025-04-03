from django.contrib import admin
from django.urls import path, include
from app.api.routes import api_urls
from web.views import dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),  # Add this line for the homepage
    path('admin/', admin.site.urls),
    path('api/', include(api_urls())),
]