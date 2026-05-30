from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Debug endpoint to check environment variables
        env_vars = {
            'API_KEY': 'SET' if os.environ.get('API_KEY') else 'NOT SET',
            'API_KEY_VALUE': os.environ.get('API_KEY', 'NOT SET')[:10] + '...' if os.environ.get('API_KEY') else 'NOT SET',
            'AI_MODEL': os.environ.get('AI_MODEL', 'NOT SET'),
            'AI_BASE_URL': os.environ.get('AI_BASE_URL', 'NOT SET'),
            'VERCEL': os.environ.get('VERCEL', 'NOT SET'),
            'VERCEL_ENV': os.environ.get('VERCEL_ENV', 'NOT SET'),
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(env_vars).encode('utf-8'))
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()