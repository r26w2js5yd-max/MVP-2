# Backend API key storage and local AI runner

1. Copy `.env.example` to `.env`.
2. Replace `your_api_key_here` with your real API key.
3. Start the local site/backend with:
   `python3 backend/server.py`
4. Open `http://127.0.0.1:8000/` in your browser.

The app loads `API_KEY`, `AI_MODEL`, and `AI_BASE_URL` from `backend/.env` and uses them for the `/api/generate-plan` endpoint.

Keep `.env` local and never commit it.
