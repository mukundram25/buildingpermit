from app import app
from werkzeug.wrappers import Response
from werkzeug.wsgi import get_current_url
import json

def handler(request):
    """Handle requests to the Vercel serverless function."""
    # Create WSGI environment
    environ = {
        'REQUEST_METHOD': request.method,
        'SCRIPT_NAME': '',
        'PATH_INFO': request.path,
        'QUERY_STRING': request.query_string.decode('utf-8') if request.query_string else '',
        'SERVER_NAME': request.host.split(':')[0] if ':' in request.host else request.host,
        'SERVER_PORT': request.host.split(':')[1] if ':' in request.host else '80',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'http',
        'wsgi.input': request.body,
        'wsgi.errors': None,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }

    # Add headers
    for key, value in request.headers.items():
        environ[f'HTTP_{key.upper().replace("-", "_")}'] = value

    # Add content type and length
    if 'content-type' in request.headers:
        environ['CONTENT_TYPE'] = request.headers['content-type']
    if 'content-length' in request.headers:
        environ['CONTENT_LENGTH'] = request.headers['content-length']

    # Response data
    response_data = []
    response_headers = []
    response_status = None

    def start_response(status, headers, exc_info=None):
        nonlocal response_status
        response_status = status
        response_headers.extend(headers)
        return response_data.append

    # Call the WSGI application
    result = app(environ, start_response)
    
    # Get the response body
    response_body = b''.join(result)
    if response_data:
        response_body = b''.join(response_data)

    # Create the response
    return Response(
        response=response_body,
        status=response_status,
        headers=response_headers
    ) 