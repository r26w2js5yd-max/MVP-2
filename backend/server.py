from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
HTML_FILE = ROOT / '01- site mvp.html'
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
        elif event_name == 'plan_generation_failure':
            totals['generated'] += 0
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


def build_prompt(answers):
    lines = [
        'You are a supportive strength coach building a personalized workout plan.',
        'Use the answers below to create a practical plan with week structure, training focus, cardio, and recovery cues.',
        'Keep it concise, motivating, and easy to follow.'
    ]

    for item in answers:
        question = item.get('question', 'Unknown question')
        answer = item.get('answer', 'No answer')
        lines.append(f"- {question}: {answer}")

    lines.append('Return only the workout plan as plain text with headings and bullet points.')
    return '\n'.join(lines)


def generate_plan(prompt):
    api_key = os.getenv('API_KEY')
    model = os.getenv('AI_MODEL', 'gpt-4o-mini')
    base_url = os.getenv('AI_BASE_URL', 'https://api.openai.com/v1')

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
                'content': 'You are a fitness coach who creates clear, safe, personalized workout plans.'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.4,
        'max_tokens': 500
    }

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            body = response.read().decode('utf-8')
            result = json.loads(body)
            content = result['choices'][0]['message']['content'].strip()
            if content:
                return {
                    'plan': content,
                    'source': 'provider'
                }
    except (urllib.error.HTTPError, urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError):
        pass

    return {
        'plan': fallback_plan(prompt),
        'source': 'fallback',
        'warning': 'The AI provider request failed, so the fallback plan is shown. Check your key and network connection.'
    }


def fallback_plan(prompt):
    summary = []
    summary.append('Your custom strength plan')
    summary.append('- Focus: 4 strength sessions each week with 1 light recovery day and 1 active recovery walk.')
    summary.append('- Structure: full-body work on alternate days, keeping rest intervals around 60–90 seconds.')
    summary.append('- Progression: increase load or reps over time, aiming for steady improvement and good recovery.')
    summary.append('- Recovery: hydrate, sleep 7–9 hours, and keep mobility work short and consistent.')
    summary.append('If you want, I can turn this into a 4-week schedule or add exercise selection by equipment.')
    return '\n'.join(summary)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 8000), BackendHandler)
    print('Server running at http://127.0.0.1:8000/')
    server.serve_forever()


if __name__ == '__main__':
    main()
