const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const dotenv = require('dotenv');

// Load environment variables from the .env file in the same directory
dotenv.config({ path: path.join(__dirname, '.env') });

const app = express();
const PORT = 8000;
const ANALYTICS_FILE = path.join(__dirname, 'analytics_events.jsonl');
const ANALYTICS_DASHBOARD = path.join(__dirname, 'analytics_dashboard.html');

app.use(cors());
app.use(express.json());

// Helper: Append analytics event to file
function appendAnalytics(payload) {
    try {
        fs.appendFileSync(ANALYTICS_FILE, JSON.stringify(payload) + '\n', 'utf8');
    } catch (err) {
        console.error('Failed to write analytics:', err);
    }
}

// Helper: AI Prompt Builder - Creates a detailed prompt for structured output
function buildPrompt(answers) {
    // Extract key answers for personalization
    const getAnswer = (keyword) => {
        const item = (answers || []).find(a => (a.question || '').toLowerCase().includes(keyword));
        return item ? item.answer || 'Not specified' : 'Not specified';
    };

    const goal = getAnswer('goal');
    const experience = getAnswer('experience');
    const frequency = getAnswer('frequency');
    const equipment = getAnswer('equipment');
    const trainingStyle = getAnswer('style');
    const sessionLength = getAnswer('session');
    const limitations = getAnswer('limitation');
    const cardio = getAnswer('cardio');

    // Extract number of days from frequency
    const daysMap = { '2 days': 2, '3 days': 3, '4 days': 4, '5 days': 5, '6–7 days': 6 };
    const numDays = daysMap[frequency] || 3;

    // Extract duration
    const durationMap = {
        '20 minutes': '20-25 min',
        '30 minutes': '30-35 min',
        '45 minutes': '45-50 min',
        '60 minutes': '55-60 min',
        '75+ minutes': '60-75 min'
    };
    const duration = durationMap[sessionLength] || '45-50 min';

    // Build equipment list context
    const equipmentContext = {
        'Full gym': 'barbells, dumbbells, cables, machines, benches',
        'Dumbbells only': 'a set of dumbbells',
        'Bodyweight only': 'no equipment, bodyweight exercises only',
        'Home gym (bench + barbell)': 'a bench, barbell, and weight plates',
        'Resistance bands': 'resistance bands of various tensions'
    };
    const availableEquipment = equipmentContext[equipment] || 'basic gym equipment';

    // Build limitation context
    const limitationAdvice = {
        'None': 'No modifications needed.',
        'Knees': 'Avoid high-impact knee exercises; focus on low-impact movements.',
        'Lower back': 'Avoid heavy spinal loading; emphasize core stability.',
        'Shoulders': 'Avoid overhead pressing if painful; focus on scapular health.',
        'Other': 'Modify exercises as needed to avoid pain.'
    };
    const limitationNote = limitationAdvice[limitations] || 'Modify as needed.';

    return `You are a supportive, certified strength and conditioning coach. Create a personalized ${numDays}-day weekly workout plan.

CLIENT PROFILE:
- Goal: ${goal}
- Experience: ${experience}
- Training days per week: ${numDays}
- Session duration: ${duration}
- Available equipment: ${availableEquipment}
- Training style preference: ${trainingStyle}
- Cardio preference: ${cardio}
- Limitations: ${limitations} (${limitationNote})

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

Now create the personalized plan:`;
}

// Helper: AI Generator
async function generatePlanAI(prompt) {
    const apiKey = process.env.API_KEY;
    const model = process.env.AI_MODEL || 'gpt-4o-mini';
    const baseUrl = (process.env.AI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, '');

    if (!apiKey || apiKey.toLowerCase() === 'your_api_key_here' || apiKey.includes('...')) {
        return { plan: fallbackPlan(prompt), source: 'fallback', warning: 'API key is not configured. Using a template plan.' };
    }

    try {
        const response = await fetch(`${baseUrl}/chat/completions`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model: model,
                messages: [
                    { role: 'system', content: 'You are a certified strength and conditioning coach who creates safe, effective, personalized workout plans. Always follow the requested format exactly.' },
                    { role: 'user', content: prompt }
                ],
                temperature: 0.3,
                max_tokens: 1500
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            return { plan: fallbackPlan(prompt), source: 'fallback', warning: `AI API error (${response.status}): ${errorText.slice(0, 200)}` };
        }

        const data = await response.json();
        const content = data.choices?.[0]?.message?.content?.trim();
        
        if (content) {
            return { plan: content, source: 'provider' };
        } else {
            return { plan: fallbackPlan(prompt), source: 'fallback', warning: 'AI returned empty response. Using template plan.' };
        }
    } catch (e) {
        return { plan: fallbackPlan(prompt), source: 'fallback', warning: `Request failed: ${e.message}` };
    }
}

function fallbackPlan(prompt) {
    return [
        'Day 1: Full Body Strength - 45-50 min',
        'This day establishes a foundation with compound movements.',
        '- Squat: 3x8-10',
        '- Bench Press: 3x8-10',
        '- Bent Over Row: 3x8-10',
        '- Plank: 3x30s',
        'Focus on controlled tempo and full range of motion.',
        '',
        'Day 2: Active Recovery - 30 min',
        'Light activity to promote recovery and mobility.',
        '- Walking: 20-30 min',
        '- Gentle stretching: 10 min',
        'Keep intensity low and focus on movement quality.',
        '',
        'Day 3: Upper Body - 45-50 min',
        'Upper body focus with pushing and pulling balance.',
        '- Overhead Press: 3x8-10',
        '- Pull-ups or Rows: 3x8-10',
        '- Push-ups: 3x10-15',
        '- Face Pulls: 3x12-15',
        'Maintain good posture throughout.',
        '',
        'Day 4: Lower Body - 45-50 min',
        'Lower body strength and stability work.',
        '- Romanian Deadlift: 3x8-10',
        '- Lunges: 3x10 each leg',
        '- Calf Raises: 3x15-20',
        '- Bird Dog: 3x10 each side',
        'Control the descent on all movements.',
        '',
        'Note: This is a template plan. For a fully personalized plan, ensure the AI API is properly configured.'
    ].join('\n');
}

// Helper: Summarize Analytics
function summarizeAnalytics() {
    const events = [];
    if (fs.existsSync(ANALYTICS_FILE)) {
        const content = fs.readFileSync(ANALYTICS_FILE, 'utf8');
        content.split('\n').forEach(line => {
            if (line.trim()) {
                try { events.push(JSON.parse(line)); } catch (e) {}
            }
        });
    }

    const byEvent = {};
    const totals = {
        starts: 0, completed: 0, attempts: 0,
        generated: 0, generated_success: 0,
        viewed: 0, returning: 0, abandoned: 0,
    };

    events.forEach(event => {
        const name = event.event;
        byEvent[name] = (byEvent[name] || 0) + 1;

        if (name === 'onboarding_started') totals.starts++;
        else if (name === 'onboarding_completed') totals.completed++;
        else if (name === 'plan_generation_attempt') totals.attempts++;
        else if (name === 'plan_generation_success') {
            totals.generated++;
            totals.generated_success++;
        }
        else if (name === 'plan_viewed') totals.viewed++;
        else if (name === 'return_visit') totals.returning++;
        else if (name === 'onboarding_abandoned') totals.abandoned++;
    });

    return {
        byEvent,
        total: totals,
        events: events.length
    };
}

// API Endpoints
app.get('/health', (req, res) => res.json({ status: 'ok' }));

app.post('/api/track', (req, res) => {
    appendAnalytics(req.body);
    res.json({ status: 'ok' });
});

app.post('/api/generate-plan', async (req, res) => {
    const { answers } = req.body;
    const prompt = buildPrompt(answers);
    const result = await generatePlanAI(prompt);
    res.json(result);
});

app.get('/api/analytics-summary', (req, res) => {
    res.json(summarizeAnalytics());
});

app.get('/analytics', (req, res) => {
    if (fs.existsSync(ANALYTICS_DASHBOARD)) {
        res.sendFile(ANALYTICS_DASHBOARD);
    } else {
        res.status(404).send('Dashboard not found');
    }
});

app.listen(PORT, '127.0.0.1', () => {
    console.log(`Backend server running at http://127.0.0.1:${PORT}`);
    if (!process.env.API_KEY) {
        console.warn('WARNING: API_KEY is not set in backend/.env - using fallback plans');
    }
});