const apiKey = process.env.API_KEY;

if (!apiKey) {
  console.warn('API_KEY is not set. Add it to your environment or backend/.env before running this backend.');
}

console.log('Backend ready. API key loaded:', Boolean(apiKey));
