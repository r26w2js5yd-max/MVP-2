from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Initialize default summary structure
        summary = {
            "total": {
                "starts": 0,
                "completed": 0,
                "generated": 0,
                "generated_success": 0,
                "viewed": 0,
                "returning": 0,
                "attempts": 0
            },
            "byEvent": {}
        }
        
        # Try to read from analytics_events.jsonl file if it exists
        analytics_file = 'analytics_events.jsonl'
        if os.path.exists(analytics_file):
            try:
                with open(analytics_file, 'r') as f:
                    events = []
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                events.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                    
                    # Count events by type
                    event_counts = {}
                    for event in events:
                        event_type = event.get('event', 'unknown')
                        event_counts[event_type] = event_counts.get(event_type, 0) + 1
                    
                    # Calculate totals based on event types
                    summary["total"]["starts"] = event_counts.get('onboarding_started', 0)
                    summary["total"]["completed"] = event_counts.get('onboarding_completed', 0)
                    summary["total"]["generated"] = event_counts.get('plan_generated', 0)
                    summary["total"]["generated_success"] = event_counts.get('plan_generated_success', 0)
                    summary["total"]["viewed"] = event_counts.get('plan_viewed', 0)
                    summary["total"]["returning"] = event_counts.get('user_returned', 0)
                    summary["total"]["attempts"] = event_counts.get('generation_attempt', 0)
                    summary["byEvent"] = event_counts
            except Exception as e:
                # If reading fails, return empty summary
                pass
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(summary).encode('utf-8'))
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()