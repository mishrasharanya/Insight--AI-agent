# InsightAI / PI-agent

InsightAI is a personal research assistant that ingests files and selected Google Workspace data, retrieves relevant evidence, and answers questions with source context. Version 1 uses FastAPI, React, Supabase/PostgreSQL with pgvector, Gemini embeddings, LangGraph, and Groq-hosted generation.

## Run locally

1. Create the backend environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

2. Fill in `.env`, then create the database objects by running `supabase_schema.sql` in the Supabase SQL editor.

3. Start the backend:

   ```bash
   uvicorn api:app --reload
   ```

4. Start the frontend in another terminal:

   ```bash
   cd insights-frontend
   yarn install
   printf 'REACT_APP_INSIGHT_API_URL=http://localhost:8000\n' > .env.local
   yarn start
   ```

The frontend runs at `http://localhost:3000` and the API at `http://localhost:8000`.

## Deploy v1

The repository is ready for a split deployment: deploy the FastAPI root as a Python web service with `uvicorn api:app --host 0.0.0.0 --port $PORT`, and deploy `insights-frontend` as a React static site. Configure the backend variables from `.env.example`; configure `REACT_APP_INSIGHT_API_URL` on the frontend with the public backend URL. Set `FRONTEND_URL` to the public frontend origin and update the Google OAuth redirect URI to the backend callback URL.

Never expose `SUPABASE_SERVICE_KEY`, `FERNET_KEY`, or model/provider keys to the frontend.

## Versions

- `v1.0.0`: deployable Supabase/pgvector implementation.
- `v3-antfly`: Antfly-backed successor work.
