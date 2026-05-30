from http.server import BaseHTTPRequestHandler
import json
import os
from datetime import datetime

def get_emails_file_path():
    """Get the path to the emails file, handling both local and Vercel environments."""
    # In Vercel serverless, we need to use /tmp directory for writable storage
    # But for persistence, we'll try the backend directory first (works in development)
    backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'emails.jsonl')
    tmp_path = '/tmp/emails.jsonl'
    
    # Try backend path first (for local dev and when writable)
    try:
        test_dir = os.path.dirname(backend_path)
        if os.access(test_dir, os.W_OK):
            return backend_path
    except:
        pass
    
    # Fall back to /tmp (Vercel serverless)
    return tmp_path

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
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
            
            # Get the appropriate file path
            emails_file = get_emails_file_path()
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(emails_file), exist_ok=True)
            
            # Append to the emails file
            with open(emails_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(email_data, ensure_ascii=True) + '\n')
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_msg = f"Server error: {str(e)}"
            self.wfile.write(json.dumps({'status': 'error', 'message': error_msg}).encode())
