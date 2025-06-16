from flask import Flask, request
from app import app
from werkzeug.wrappers import Response
from werkzeug.serving import run_simple
import sys

# This is the entry point for Vercel
def handler(request):
    """Handle requests to the Vercel serverless function."""
    environ = {
        'REQUEST_METHOD': request.method,
        'SCRIPT_NAME': '',
        'PATH_INFO': request.path,
        'QUERY_STRING': request.query_string.decode('utf-8'),
        'SERVER_NAME': request.host.split(':')[0],
        'SERVER_PORT': request.host.split(':')[1] if ':' in request.host else '80',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'http',
        'wsgi.input': request.body,
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
        'CONTENT_TYPE': request.headers.get('Content-Type', ''),
        'CONTENT_LENGTH': str(len(request.body or '')),
        'HTTP_HOST': request.host,
    }
    
    # Add headers
    for key, value in request.headers.items():
        environ[f'HTTP_{key.upper().replace("-", "_")}'] = value

    def start_response(status, headers, exc_info=None):
        return Response(status=status, headers=headers)

    return app(environ, start_response) 