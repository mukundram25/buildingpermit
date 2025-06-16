from http.server import BaseHTTPRequestHandler
from app import app
from flask import request as flask_request
import json

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests."""
        try:
            # Create a test client
            with app.test_client() as client:
                # Make the request using Flask's test client
                response = client.get(self.path)
                
                # Send response
                self.send_response(response.status_code)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response.data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_POST(self):
        """Handle POST requests."""
        try:
            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Create a test client
            with app.test_client() as client:
                # Make the request using Flask's test client
                response = client.post(
                    self.path,
                    data=body,
                    headers=dict(self.headers)
                )
                
                # Send response
                self.send_response(response.status_code)
                for key, value in response.headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response.data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

def handler(request):
    """Entry point for Vercel serverless function."""
    return Handler() 