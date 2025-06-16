from flask import Flask, request, Response
from app import app

def handler(request):
    """Handle requests to the Vercel serverless function."""
    try:
        # Create a test client
        with app.test_client() as client:
            # Convert Vercel request to Flask request
            method = request.method
            path = request.path
            headers = dict(request.headers)
            data = request.body
            
            # Make the request using Flask's test client
            response = client.open(
                path=path,
                method=method,
                headers=headers,
                data=data
            )
            
            # Return the response in Vercel's expected format
            return {
                'statusCode': response.status_code,
                'headers': dict(response.headers),
                'body': response.data.decode('utf-8')
            }
    except Exception as e:
        # Return error response
        return {
            'statusCode': 500,
            'body': str(e)
        } 