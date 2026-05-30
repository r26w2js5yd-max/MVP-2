from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / 'index.html'
ENV_FILE = Path(__file__).resolve().parent / '.env'
ANALYTICS_FILE = Path(__file__).resolve().parent / 'analytics_events.jsonl'
ANALYTICS_DASHBOARD = Path(__file__).resolve().parent / 'analytics_dashboard.html'


def load_env(file_path: Path) -> None:
    if not file_path.exists():
        return
    for line in file_path.read_text(encoding='utf-8').splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


load_env(ENV_FILE)


def read_json_body(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    raw_body = handler.rfile.read(content_length).decode('utf-8')
    try:
        return json.loads(raw_body or '{}')
    except json.JSONDecodeError:
        return {}


def append_analytics_event(payload):
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ANALYTICS_FILE.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + '\n')


def load_analytics_events():
    if not ANALYTICS_FILE.exists():
        return []

    events = []
    with ANALYTICS_FILE.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def summarize_analytics():
    events = load_analytics_events()
    by_event = {}
    totals = {
        'starts': 0,
        'completed': 0,
        'attempts': 0,
        'generated': 0,
        'generated_success': 0,
        'viewed': 0,
        'returning': 0,
        'abandoned': 0,
    }

    for event in events:
        event_name = event.get('event')
        by_event[event_name] = by_event.get(event_name, 0) + 1

        if event_name == 'onboarding_started':
            totals['starts'] += 1
        elif event_name == 'onboarding_completed':
            totals['completed'] += 1
        elif event_name == 'plan_generation_attempt':
            totals['attempts'] += 1
        elif event_name == 'plan_generation_success':
            totals['generated'] += 1
            totals['generated_success'] += 1
        elif event_name == 'plan_viewed':
            totals['viewed'] += 1
        elif event_name == 'return_visit':
            totals['returning'] += 1
        elif event_name == 'onboarding_abandoned':
            totals['abandoned'] += 1

    return {
        'byEvent': dict(sorted(by_event.items())),
        'total': totals,
        'events': len(events),
    }


def build_prompt(answers):
    """Build a detailed prompt that guides the AI to produce structured, parseable output."""
    # Extract key answers for personalization
    goal = next((item.get('answer', '') for item in answers if 'goal' in item.get('question', '').lower()), 'general fitness')
    experience = next((item.get('answer', '') for item in answers if 'experience' in item.get('question', '').lower()), 'intermediate')
    frequency = next((item.get('answer', '') for item in answers if 'frequency' in item.get('question', '').lower()), '3 days')
    equipment = next((item.get('answer', '') for item in answers if 'equipment' in item.get('question', '').lower()), 'full gym')
    training_style = next((item.get('answer', '') for item in answers if 'style' in item.get('question', '').lower()), 'mixed')
    session_length = next((item.get('answer', '') for item in answers if 'session' in item.get('question', '').lower()), '45 minutes')
    limitations = next((item.get('answer', '') for item in answers if 'limitation' in item.get('question', '').lower()), 'none')
    cardio = next((item.get('answer', '') for item in answers if 'cardio' in item.get('question', '').lower()), 'none')

    # Extract number of days from frequency
    days_map = {'2 days': 2, '3 days': 3, '4 days': 4, '5 days': 5, '6–7 days': 6}
    num_days = days_map.get(frequency, 3)

    # Extract duration
    duration_map = {
        '20 minutes': '20-25 min',
        '30 minutes': '30-35 min', 
        '45 minutes': '45-50 min',
        '60 minutes': '55-60 min',
        '75+ minutes': '60-75 min'
    }
    duration = duration_map.get(session_length, '45-50 min')

    # Build equipment list context
    equipment_context = {
        'Full gym': 'barbells, dumbbells, cables, machines, benches',
        'Dumbbells only': 'a set of dumbbells',
        'Bodyweight only': 'no equipment, bodyweight exercises only',
        'Home gym (bench + barbell)': 'a bench, barbell, and weight plates',
        'Resistance bands': 'resistance bands of various tensions'
    }
    available_equipment = equipment_context.get(equipment, 'basic gym equipment')

    # Build limitation context
    limitation_advice = {
        'None': 'No modifications needed.',
        'Knees': 'Avoid high-impact knee exercises; focus on low-impact movements.',
        'Lower back': 'Avoid heavy spinal loading; emphasize core stability.',
        'Shoulders': 'Avoid overhead pressing if painful; focus on scapular health.',
        'Other': 'Modify exercises as needed to avoid pain.'
    }
    limitation_note = limitation_advice.get(limitations, 'Modify as needed.')

    prompt = f"""You are a supportive, certified strength and conditioning coach. Create a personalized {num_days}-day weekly workout plan.

CLIENT PROFILE:
- Goal: {goal}
- Experience: {experience}
- Training days per week: {num_days}
- Session duration: {duration}
- Available equipment: {available_equipment}
- Training style preference: {training_style}
- Cardio preference: {cardio}
- Limitations: {limitations} ({limitation_note})

OUTPUT FORMAT REQUIREMENTS:
You MUST follow this exact format for the plan to be parsed correctly:

1. Start each day on a new line with this exact format:
   "Day X: [Focus Area] - [Duration]"
   Example: "Day 1: Full Body Strength - 45-50 min"

2. After each day header, include:
   - A brief explanation of why this day is structured this way (1 sentence)
   - A bulleted list of exercises with sets x reps format
   - Any coaching notes or modifications

3. Use only these focus area names: Full Body, Upper Body, Lower Body, Push Focus, Pull Focus, Legs, Core, Conditioning, Active Recovery

4. Keep exercises appropriate for the available equipment.

5. Respect the stated limitations when selecting exercises.

EXAMPLE FORMAT:
Day 1: Full Body Strength - 45-50 min
This day establishes a foundation with compound movements targeting all major muscle groups.
- Squat: 3x8-10
- Bench Press: 3x8-10
- Bent Over Row: 3x8-10
- Plank: 3x30s
Focus on controlled tempo and full range of motion.

Now create the personalized plan:"""

    return prompt


def fallback_plan(prompt=""):
    """Generate a basic fallback plan when AI is unavailable."""
    summary = [
        "Day 1: Full Body Strength - 45-50 min",
        "This day establishes a foundation with compound movements.",
        "- Squat: 3x8-10",
        "- Bench Press: 3x8-10", 
        "- Bent Over Row: 3x8-10",
        "- Plank: 3x30s",
        "Focus on controlled tempo and full range of motion.",
        "",
        "Day 2: Active Recovery - 30 min",
        "Light activity to promote recovery and mobility.",
        "- Walking: 20-30 min",
        "- Gentle stretching: 10 min",
        "Keep intensity low and focus on movement quality.",
        "",
        "Day 3: Upper Body - 45-50 min", 
        "Upper body focus with pushing and pulling balance.",
        "- Overhead Press: 3x8-10",
        "- Pull-ups or Rows: 3x8-10",
        "- Push-ups: 3x10-15",
        "- Face Pulls: 3x12-15",
        "Maintain good posture throughout.",
        "",
        "Day 4: Lower Body - 45-50 min",
        "Lower body strength and stability work.",
        "- Romanian Deadlift: 3x8-10",
        "- Lunges: 3x10 each leg",
        "- Calf Raises: 3x15-20",
        "- Bird Dog: 3x10 each side",
        "Control the descent on all movements.",
        "",
        "Note: This is a template plan. For a fully personalized plan, ensure the AI API is properly configured."
    ]
    return '\n'.join(summary)


def generate_plan(prompt):
    """Generate a workout plan using the AI API."""
    api_key = os.getenv('API_KEY')
    model = os.getenv('AI_MODEL', 'gpt-4o-mini')
    base_url = os.getenv('AI_BASE_URL', 'https://api.openai.com/v1')

    # Check for missing or placeholder API keys
    if not api_key:
        return {
            'plan': fallback_plan(prompt),
            'source': 'fallback',
            'warning': 'API key is missing. Add a real key to backend/.env to use the AI model.'
        }

    if '...' in api_key or api_key.strip().lower() == 'your_api_key_here':
        return {
            'plan': fallback_plan(prompt),
            'source': 'fallback',
            'warning': 'The API key in backend/.env is still a placeholder. Replace it with your real secret to use the AI model.'
        }

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': 'You are a certified strength and conditioning coach who creates safe, effective, personalized workout plans. Always follow the requested format exactly.'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.3,
        'max_tokens': 1500
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            body = response.read().decode('utf-8')
            result = json.loads(body)
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
            
            if content:
                return {
                    'plan': content,
                    'source': 'provider'
                }
            else:
                return {
                    'plan': fallback_plan(prompt),
                    'source': 'fallback',
                    'warning': 'AI returned empty response. Using template plan.'
                }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else str(e)
        return {
            'plan': fallback_plan(prompt),
            'source': 'fallback',
            'warning': f'AI API error ({e.code}): {error_body[:200]}'
        }
    except Exception as e:
        return {
            'plan': fallback_plan(prompt),
            'source': 'fallback',
            'warning': f'AI request failed: {str(e)}. Check your key and network connection.'
        }


class BackendHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == '/':
            content = HTML_FILE.read_text(encoding='utf-8')
            self._send_text(200, content, 'text/html; charset=utf-8')
            return

        if self.path == '/analytics':
            if not ANALYTICS_DASHBOARD.exists():
                self._send_bytes(404, b'Not Found', 'text/plain; charset=utf-8')
                return
            content = ANALYTICS_DASHBOARD.read_text(encoding='utf-8')
            self._send_text(200, content, 'text/html; charset=utf-8')
            return

        if self.path == '/health':
            payload = json.dumps({'status': 'ok'}).encode('utf-8')
            self._send_bytes(200, payload, 'application/json')
            return

        if self.path == '/api/analytics-summary':
            payload = json.dumps(summarize_analytics()).encode('utf-8')
            self._send_bytes(200, payload, 'application/json')
            return

        if self.path == '/favicon.ico':
            self._send_bytes(404, b'Not Found', 'text/plain; charset=utf-8')
            return

        super().do_GET()

    def do_POST(self):
        if self.path == '/api/generate-plan':
            payload = read_json_body(self)
            answers = payload.get('answers') or []
            prompt = build_prompt(answers)
            result = generate_plan(prompt)
            response = json.dumps(result).encode('utf-8')
            self._send_bytes(200, response, 'application/json')
            return

        if self.path == '/api/track':
            payload = read_json_body(self)
            append_analytics_event(payload)
            response = json.dumps({'status': 'ok'}).encode('utf-8')
            self._send_bytes(200, response, 'application/json')
            return

        self._send_bytes(404, b'Not Found', 'text/plain; charset=utf-8')

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _send_text(self, status_code, text, content_type):
        data = text.encode('utf-8')
        self._send_bytes(status_code, data, content_type)

    def _send_bytes(self, status_code, data, content_type):
        self.send_response(status_code)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 8000), BackendHandler)
    print('Server running at http://127.0.0.1:8000/')
    if not os.getenv('API_KEY'):
        print('WARNING: API_KEY is not set in backend/.env - using fallback plans')
    server.serve_forever()


if __name__ == '__main__':
    main()