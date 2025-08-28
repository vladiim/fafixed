import logging

logger = logging.getLogger(__name__)

class SpikeLoggingMiddleware:
    """SPIKE: Middleware to log all requests for debugging"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log every request that comes in
        if 'refresh-status' in request.path:
            logger.info(f"🌐 SPIKE MIDDLEWARE: {request.method} {request.path}")
            logger.info(f"🌐 SPIKE MIDDLEWARE: User: {request.user}")
            logger.info(f"🌐 SPIKE MIDDLEWARE: Content-Type: {request.content_type}")
            
            if request.method == 'POST':
                logger.info(f"🌐 SPIKE MIDDLEWARE: POST data keys: {list(request.POST.keys())}")
        
        response = self.get_response(request)
        
        if 'refresh-status' in request.path:
            logger.info(f"🌐 SPIKE MIDDLEWARE: Response status: {response.status_code}")
            logger.info(f"🌐 SPIKE MIDDLEWARE: Response content-type: {response.get('Content-Type', 'N/A')}")
        
        return response