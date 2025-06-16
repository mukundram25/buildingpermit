from app import app

def handler(request, response):
    """Entry point for Vercel serverless function."""
    return app 