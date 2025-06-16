from flask import Flask, request, Response
from app import app

def handler(request):
    """Handle requests to the Vercel serverless function."""
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
        
        # Return the response
        return Response(
            response=response.data,
            status=response.status_code,
            headers=dict(response.headers)
        ) 