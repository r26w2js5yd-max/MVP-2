from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime

EMAILS_FILE = os.path.join(os.path.dirname(__file__), '..', 'backend', 'emails.jsonl')

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        raw_body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            payload = json.loads(raw_body or '{}')
        except json.JSONDecodeError:
            payload = {}
        
        email = payload.get('email', '').strip().lower()
        if not email or '@' not in email or '.' not in email:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error', 'message': 'Invalid email address'}).encode())
            return
        
        email_data = {
            'email': email,
            'timestamp': payload.get('timestamp', datetime.now().isoformat()),
            'session_id': payload.get('session_id', ''),
            'source': payload.get('source', 'workout_generator')
        }
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(EMAILS_FILE), exist_ok=True)
        
        # Append to the emails file
        with open(EMAILS_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(email_data, ensure_ascii=True) + '\n')
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'status': 'ok'}).encode())