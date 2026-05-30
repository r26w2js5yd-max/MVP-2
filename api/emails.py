from http.server import BaseHTTPRequestHandler
import json
import os

EMAILS_FILE = os.path.join(os.path.dirname(__file__), '..', 'backend', 'emails.jsonl')

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        emails = []
        
        if os.path.exists(EMAILS_FILE):
            with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        emails.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        
        # Return emails in reverse order (newest first)
        emails.reverse()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'emails': emails, 'total': len(emails)}).encode())