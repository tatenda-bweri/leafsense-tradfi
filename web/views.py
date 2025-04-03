from django.shortcuts import render

def dashboard(request):
    """Render the main dashboard view"""
    return render(request, 'index.html')