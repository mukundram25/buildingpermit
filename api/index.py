from flask import Flask, request
from app import app

# This is the entry point for Vercel
def handler(request):
    """Handle requests to the Vercel serverless function."""
    return app(request) 