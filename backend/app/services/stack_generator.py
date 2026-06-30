import logging
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

AVAILABLE_STACKS = {
    "frontend": [
        {"id": "react", "label": "React.js (Vite)", "language": "javascript"},
        {"id": "webpack", "label": "Vanilla JS (Webpack)", "language": "javascript"},
    ],
    "backend": [
        {"id": "fastapi", "label": "FastAPI (Python)", "language": "python"},
        {"id": "express", "label": "Express.js (Node)", "language": "javascript"},
    ],
    "database": [
        {"id": "mongodb", "label": "MongoDB", "language": None},
    ],
    "cache": [
        {"id": "redis", "label": "Redis", "language": None},
    ],
    "worker": [
        {"id": "rqworker", "label": "RQ Worker (Python)", "language": "python"},
        {"id": "bullworker", "label": "Bull Worker (Node)", "language": "javascript"},
    ],
}


def _merge_package_jsons(base: str, addon: str) -> str:
    try:
        base_obj = json.loads(base)
        addon_obj = json.loads(addon)
        
        for key in ["dependencies", "devDependencies", "scripts"]:
            if key in addon_obj:
                base_obj[key] = {**base_obj.get(key, {}), **addon_obj[key]}
        
        return json.dumps(base_obj, indent=2)
    except json.JSONDecodeError:
        return base


def _merge_requirements(base: str, addon: str) -> str:
    base_lines = [l.strip() for l in base.strip().split('\n') if l.strip()]
    addon_lines = [l.strip() for l in addon.strip().split('\n') if l.strip()]
    
    combined = base_lines + [l for l in addon_lines if l not in base_lines]
    return '\n'.join(combined) + '\n'


def generate_project(tech_stack: Dict[str, str]) -> Dict[str, Any]:
    frontend = tech_stack.get("frontend", "")
    backend = tech_stack.get("backend", "")
    database = tech_stack.get("database", "")
    cache = tech_stack.get("cache", "")
    worker = tech_stack.get("worker", "")

    files: Dict[str, str] = {}
    services: List[str] = []

    if frontend:
        files.update(_gen_frontend(frontend))
        services.append("frontend")

    if backend:
        files.update(_gen_backend(backend))
        services.append("backend")

    if database:
        services.append(database)

    if cache:
        services.append(cache)

    if worker and backend:
        worker_files = _gen_worker(worker, backend)
        files.update(worker_files)
        services.append(worker)
        
        if worker == "bullworker" and backend == "express":
            base_pkg = files.get("backend/package.json", "{}")
            addon_pkg = worker_files.get("backend/package.json.bullmq", "{}")
            files["backend/package.json"] = _merge_package_jsons(base_pkg, addon_pkg)
            if "backend/package.json.bullmq" in files:
                del files["backend/package.json.bullmq"]
        
        if worker == "rqworker" and backend == "fastapi":
            base_req = files.get("backend/requirements.txt", "")
            addon_req = worker_files.get("backend/requirements.txt.rq", "")
            files["backend/requirements.txt"] = _merge_requirements(base_req, addon_req)
            if "backend/requirements.txt.rq" in files:
                del files["backend/requirements.txt.rq"]

    files["docker-compose.yml"] = _gen_compose(frontend, backend, database, cache, worker)

    meta = {
        "frontend": frontend,
        "backend": backend,
        "database": database,
        "cache": cache,
        "worker": worker,
        "services": services,
    }

    return {"files": files, "meta": meta, "composeContent": files["docker-compose.yml"]}


# ---------------------------------------------------------------------------
# docker-compose.yml
# ---------------------------------------------------------------------------

def _gen_compose(frontend: str, backend: str, database: str, cache: str, worker: str) -> str:
    services: List[str] = []

    if frontend:
        services.append(f"""  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    environment:
      - VITE_API_URL=/api
    command: ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
    networks:
      - session-net
      - nginx-proxy
    restart: unless-stopped""")

    if backend == "fastapi":
        cmd = '["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000", "--reload"]'
    elif backend == "express":
        cmd = '["npm", "run", "dev"]'
    else:
        cmd = '["sleep", "infinity"]'

    if backend:
        deps = []
        if database:
            deps.append("      - " + database)
        if cache:
            deps.append("      - " + cache)

        depends = ""
        if deps:
            depends = "\n    depends_on:\n" + "\n".join(deps)

        env_lines = []
        if database == "mongodb":
            env_lines.append("      - MONGO_URL=mongodb://mongodb:27017")
            env_lines.append("      - DB_NAME=app")
        if cache == "redis":
            env_lines.append("      - REDIS_URL=redis://redis:6379/0")
        env_block = "\n".join(env_lines) if env_lines else "      - APP_ENV=development"

        services.append(f"""  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app{depends}
    environment:
{env_block}
    command: {cmd}
    networks:
      - session-net
      - nginx-proxy
    restart: unless-stopped""")

    if worker == "rqworker" and backend == "fastapi":
        services.append(f"""  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
    environment:
      - REDIS_URL=redis://redis:6379/0
    command: ["rq", "worker", "--url", "redis://redis:6379/0"]
    depends_on:
      - redis
    networks:
      - session-net
    restart: unless-stopped""")
    elif worker == "bullworker" and backend == "express":
        services.append(f"""  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    volumes:
      - ./backend:/app
    environment:
      - REDIS_URL=redis://redis:6379/0
    command: ["node", "worker.js"]
    depends_on:
      - redis
    networks:
      - session-net
    restart: unless-stopped""")

    if database == "mongodb":
        services.append("""  mongodb:
    image: mongo:7
    volumes:
      - mongo_data:/data/db
    networks:
      - session-net
    restart: unless-stopped""")

    if cache == "redis":
        services.append("""  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    networks:
      - session-net
    restart: unless-stopped""")

    volumes = []
    if database == "mongodb":
        volumes.append("  mongo_data:")
    if cache == "redis":
        volumes.append("  redis_data:")

    result = "version: '3.8'\n\nservices:\n"
    result += "\n\n".join(services)

    if volumes:
        result += "\n\nvolumes:\n" + "\n".join(volumes)

    result += "\n\nnetworks:\n  session-net:\n    driver: bridge\n  nginx-proxy:\n    external: true\n    name: development_default\n"
    return result


# ---------------------------------------------------------------------------
# Frontend generators
# ---------------------------------------------------------------------------

def _gen_frontend(framework: str) -> Dict[str, str]:
    if framework == "react":
        return _gen_react_frontend()
    elif framework == "webpack":
        return _gen_webpack_frontend()
    return {}


def _gen_react_frontend() -> Dict[str, str]:
    return {
        "frontend/Dockerfile.dev": """FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
""",
        "frontend/package.json": """{
  "name": "student-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "vite": "^5.0.0"
  }
}
""",
        "frontend/vite.config.js": """import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  return {
    plugins: [react()],
    base: env.VITE_BASE_URL || '/',
    server: {
      host: '0.0.0.0',
      port: 5173,
    }
  }
})
""",
        "frontend/index.html": """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Student App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
""",
        "frontend/src/main.jsx": """import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
""",
        "frontend/src/App.jsx": """import { useState, useEffect } from 'react'

const API_URL = import.meta.env.VITE_API_URL || ''

function App() {
  const [data, setData] = useState(null)

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then(res => res.json())
      .then(setData)
      .catch(() => setData({ status: 'backend not connected' }))
  }, [])

  return (
    <div style={{ maxWidth: 600, margin: '40px auto', fontFamily: 'sans-serif' }}>
      <h1>My App</h1>
      <p>Backend status: {data?.status || 'loading...'}</p>
    </div>
  )
}

export default App
""",
        "frontend/src/index.css": """body {
  margin: 0;
  font-family: Inter, system-ui, sans-serif;
  background: #f9fafb;
  color: #111827;
}
""",
    }


def _gen_webpack_frontend() -> Dict[str, str]:
    return {
        "frontend/Dockerfile.dev": """FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 8080

CMD ["npm", "run", "dev"]
""",
        "frontend/package.json": """{
  "name": "student-frontend",
  "private": true,
  "version": "0.0.0",
  "scripts": {
    "dev": "webpack serve --mode development",
    "build": "webpack --mode production"
  },
  "devDependencies": {
    "webpack": "^5.90.0",
    "webpack-cli": "^5.1.4",
    "webpack-dev-server": "^5.0.0",
    "html-webpack-plugin": "^5.6.0",
    "css-loader": "^7.0.0",
    "style-loader": "^4.0.0"
  }
}
""",
        "frontend/webpack.config.js": """const path = require('path')
const HtmlWebpackPlugin = require('html-webpack-plugin')

module.exports = {
  entry: './src/index.js',
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
  },
  module: {
    rules: [
      { test: /\\.css$/, use: ['style-loader', 'css-loader'] },
    ],
  },
  plugins: [
    new HtmlWebpackPlugin({ template: './src/index.html' }),
  ],
  devServer: {
    host: '0.0.0.0',
    port: 8080,
    hot: true,
  },
}
""",
        "frontend/src/index.html": """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Student App</title>
</head>
<body>
  <div id="root">
    <h1>My App</h1>
    <p>Vanilla JS with Webpack</p>
  </div>
</body>
</html>
""",
        "frontend/src/index.js": """import './style.css'

async function checkHealth() {
  try {
    const res = await fetch('/api/health')
    const data = await res.json()
    document.getElementById('status').textContent = data.status || 'unknown'
  } catch {
    document.getElementById('status').textContent = 'backend not connected'
  }
}

checkHealth()
""",
        "frontend/src/style.css": """body {
  font-family: Inter, system-ui, sans-serif;
  background: #f9fafb;
  color: #111827;
  max-width: 600px;
  margin: 40px auto;
}
""",
    }


# ---------------------------------------------------------------------------
# Backend generators
# ---------------------------------------------------------------------------

def _gen_backend(framework: str) -> Dict[str, str]:
    if framework == "fastapi":
        return _gen_fastapi_backend()
    elif framework == "express":
        return _gen_express_backend()
    return {}


def _gen_fastapi_backend() -> Dict[str, str]:
    return {
        "backend/Dockerfile.dev": """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7000", "--reload"]
""",
        "backend/requirements.txt": """fastapi==0.109.0
uvicorn[standard]==0.27.0
pymongo==4.6.0
redis==5.0.1
pydantic==2.5.3
""",
        "backend/app/__init__.py": "",
        "backend/app/main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "app")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "fastapi"}
""",
    }


def _gen_express_backend() -> Dict[str, str]:
    return {
        "backend/Dockerfile.dev": """FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 7000

CMD ["npm", "run", "dev"]
""",
        "backend/package.json": """{
  "name": "student-backend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "node --watch index.js",
    "start": "node index.js"
  },
  "dependencies": {
    "express": "^4.19.0",
    "cors": "^2.8.5",
    "mongoose": "^8.1.0",
    "ioredis": "^5.4.0"
  }
}
""",
        "backend/index.js": """import express from 'express'
import cors from 'cors'

const app = express()

app.use(cors({ origin: '*' }))
app.use(express.json())

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', service: 'express' })
})

const PORT = process.env.PORT || 7000
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on port ${PORT}`)
})
""",
    }


# ---------------------------------------------------------------------------
# Worker generators
# ---------------------------------------------------------------------------

def _gen_worker(worker: str, backend: str) -> Dict[str, str]:
    if worker == "rqworker" and backend == "fastapi":
        return {
            "backend/app/worker.py": '''import os
from rq import Queue, Worker
from redis import Redis

redis_conn = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
queue = Queue("default", connection=redis_conn)

if __name__ == "__main__":
    worker = Worker([queue], connection=redis_conn)
    worker.work()
''',
            "backend/requirements.txt.rq": """rq==1.15.0
""",
        }
    elif worker == "bullworker" and backend == "express":
        return {
            "backend/worker.js": """import Redis from 'ioredis'
import { Queue, Worker } from 'bullmq'

const connection = new Redis(process.env.REDIS_URL || 'redis://redis:6379/0')

const queue = new Queue('default', { connection })

const worker = new Worker('default', async (job) => {
  console.log('Processing job:', job.id, job.data)
}, { connection })

worker.on('completed', (job) => {
  console.log('Job completed:', job.id)
})

worker.on('failed', (job, err) => {
  console.log('Job failed:', job.id, err.message)
})

console.log('Worker started, listening for jobs...')
""",
            "backend/package.json.bullmq": """{
  "dependencies": {
    "bullmq": "^5.0.0"
  }
}
""",
        }
    return {}
