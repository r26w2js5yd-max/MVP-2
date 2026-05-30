from http.server import BaseHTTPRequestHandler
import json
import os

def get_emails_file_path():
    """Get the path to the emails file, handling both local and Vercel environments."""
    backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'emails.jsonl')
    tmp_path = '/tmp/emails.jsonl'
    
    # Check both locations and return whichever exists
    if os.path.exists(backend_path):
        return backend_path
    if os.path.exists(tmp_path):
        return tmp_path
    
    # Default to backend path
    return backend_path

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        emails = []
        emails_file = get_emails_file_path()
        
        if os.path.exists(emails_file):
            with open(emails_file, 'r', encoding='utf-8') as f:
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
