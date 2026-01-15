#!/usr/bin/env python3
"""
Simple static file server for frontend
"""
import os
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

class FrontendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.getcwd(), **kwargs)
    
    def guess_type(self, path):
        """Override to handle custom MIME types"""
        mimetype, encoding = mimetypes.guess_type(path)
        
        # Handle common web file extensions
        if path.endswith('.js'):
            return 'application/javascript'
        elif path.endswith('.css'):
            return 'text/css'
        elif path.endswith('.html'):
            return 'text/html'
        elif path.endswith('.json'):
            return 'application/json'
        
        return mimetype or 'application/octet-stream'
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def main():
    port = int(os.environ.get('PORT', 3000))
    host = os.environ.get('HOST', 'localhost')
    
    # Change to frontend directory
    os.chdir(Path(__file__).parent.absolute())
    
    print(f"Starting frontend server on http://{host}:{port}")
    print(f"Serving files from: {os.getcwd()}")
    
    server = HTTPServer((host, port), FrontendHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

if __name__ == '__main__':
    main()