# Générateur de sites web IA

Application pédagogique permettant à des élèves de générer un site HTML/CSS complet à partir d'un prompt textuel.

## Architecture

```
backend/    → API FastAPI + agent LangGraph (Python)
frontend/   → Interface Vue 3 + Tailwind CSS v4 (Vite)
```

## Démarrage rapide

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Éditez .env et renseignez OPENROUTER_API_KEY
uvicorn app.main:app --reload
```

L'API sera disponible sur `http://localhost:8000`.
Vérification : `GET http://localhost:8000/api/health`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env        # contient VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

L'interface sera disponible sur `http://localhost:5173`.

## Variables d'environnement

### `backend/.env`

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | Clé API OpenRouter (obligatoire) |
| `MODEL_NAME` | Modèle utilisé (défaut : `deepseek/deepseek-v4-flash`) |
| `FRONTEND_ORIGIN` | Origine autorisée pour CORS (défaut : `http://localhost:5173`) |
| `MAX_RETRIES` | Nombre maximum de relances de l'agent (défaut : `2`) |

### `frontend/.env`

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | URL de base du backend |

## Déploiement

**Option A — Service unique (recommandé pour une classe)**

Construisez le frontend, puis servez `frontend/dist/` via FastAPI :

```bash
cd frontend && npm run build
# Dans backend/app/main.py, ajouter :
# from fastapi.staticfiles import StaticFiles
# app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")
```

Déployer le backend sur Render/Railway/Fly.io, configurer `VITE_API_BASE_URL` vers l'URL publique.

**Option B — Services séparés**

- Backend sur un PaaS Python (Render, Railway, PythonAnywhere…)
- Frontend sur Netlify/Vercel/GitHub Pages avec `VITE_API_BASE_URL` pointant vers le backend
- Mettre à jour `FRONTEND_ORIGIN` dans le `.env` du backend avec l'URL publique du frontend

## API

- `POST /api/generate` — corps `{"prompt": "..."}` (multipart/form-data)
- `GET /api/health` — vérification de disponibilité
