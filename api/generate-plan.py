from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.error

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


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            payload = json.loads(body or '{}')
        except json.JSONDecodeError:
            payload = {}
        
        answers = payload.get('answers') or []
        prompt = build_prompt(answers)
        
        # Get configuration from environment variables
        api_key = os.environ.get('API_KEY')
        model = os.environ.get('AI_MODEL', 'gpt-4o-mini')
        base_url = os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1')

        # Check for missing or placeholder API keys
        if not api_key or api_key.strip().lower() == 'your_api_key_here' or '...' in api_key:
            result = {
                'plan': fallback_plan(prompt), 
                'source': 'fallback', 
                'warning': 'API key is not configured. Using a template plan.'
            }
        else:
            url = f"{base_url.rstrip('/')}/chat/completions"
            ai_payload = {
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are a certified strength and conditioning coach who creates safe, effective, personalized workout plans. Always follow the requested format exactly.'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 1500
            }
            
            req = urllib.request.Request(
                url, 
                data=json.dumps(ai_payload).encode('utf-8'),
                headers={
                    'Authorization': f'Bearer {api_key}', 
                    'Content-Type': 'application/json'
                },
                method='POST'
            )

            try:
                with urllib.request.urlopen(req, timeout=90) as response:
                    res_body = json.loads(response.read().decode('utf-8'))
                    content = res_body.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                    
                    if content:
                        result = {'plan': content, 'source': 'provider'}
                    else:
                        result = {
                            'plan': fallback_plan(prompt),
                            'source': 'fallback',
                            'warning': 'AI returned empty response. Using template plan.'
                        }
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8') if e.fp else str(e)
                result = {
                    'plan': fallback_plan(prompt), 
                    'source': 'fallback',
                    'warning': f'AI API error ({e.code}): {error_body[:200]}'
                }
            except Exception as e:
                result = {
                    'plan': fallback_plan(prompt), 
                    'source': 'fallback',
                    'warning': f'AI request failed: {str(e)}'
                }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()