from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error

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

def fallback_plan(prompt=""):
    summary = [
        "Your custom strength plan",
        "- Focus: 4 strength sessions each week with 1 light recovery day and 1 active recovery walk.",
        "- Structure: full-body work on alternate days, keeping rest intervals around 60–90 seconds.",
        "- Progression: increase load or reps over time, aiming for steady improvement and good recovery.",
        "- Recovery: hydrate, sleep 7–9 hours, and keep mobility work short and consistent.",
        "If you want, I can turn this into a 4-week schedule or add exercise selection by equipment."
    ]
    return '\n'.join(summary)

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        payload = json.loads(body or '{}')
        
        answers = payload.get('answers') or []
        prompt = build_prompt(answers)
        
        api_key = os.environ.get('API_KEY')
        model = os.environ.get('AI_MODEL', 'gpt-4o-mini')
        base_url = os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1')

        if not api_key:
            result = {'plan': fallback_plan(), 'source': 'fallback', 'warning': 'API key missing'}
        else:
            url = f"{base_url.rstrip('/')}/chat/completions"
            ai_payload = {
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are a fitness coach.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.4,
                'max_tokens': 500
            }
            
            req = urllib.request.Request(
                url, 
                data=json.dumps(ai_payload).encode('utf-8'),
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                method='POST'
            )

            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    content = res_body['choices'][0]['message']['content'].strip()
                    result = {'plan': content, 'source': 'provider'}
            except Exception:
                result = {'plan': fallback_plan(), 'source': 'fallback'}

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))