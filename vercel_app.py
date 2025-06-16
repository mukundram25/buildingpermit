import logging
from app import app
from flask import request

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# This is the entry point for Vercel
def handler(request):
    """Handle requests to the Vercel serverless function."""
    try:
        logger.info("Received request in Vercel handler")
        response = app(request)
        logger.info("Request processed successfully")
        return response
    except Exception as e:
        logger.error(f"Error in Vercel handler: {str(e)}")
        return {
            "statusCode": 500,
            "body": str(e),
            "headers": {
                "Content-Type": "application/json"
            }
        } 