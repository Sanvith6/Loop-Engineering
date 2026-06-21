# Maker Output
```yaml docker-compose.yml
version: "2.4"

services:
  database:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: storage
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app_password
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d storage"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - backend-network

  backend:
    build:
      context: ./backend
    restart: unless-stopped
    environment:
      NODE_ENV: production
      PORT: 3000
      DB_HOST: database
      DB_PORT: 5432
      DB_NAME: storage
      DB_USER: app
      DB_PASSWORD: app_password
      CORS_ORIGIN: "http://localhost:8080,http://127.0.0.1:8080,http://0.0.0.0:8080"
    ports:
      - "3000:3000"
    depends_on:
      database:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "node -e \"fetch('http://127.0.0.1:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\""]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - frontend-network
      - backend-network

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: "http://localhost:3000/api"
    restart: unless-stopped
    ports:
      - "8080:8080"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1:8080/healthz >/dev/null 2>&1 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 5s
    networks:
      - frontend-network

networks:
  frontend-network:
    driver: bridge
  backend-network:
    driver: bridge

volumes:
  postgres-data:
```

```dockerfile backend/Dockerfile
# syntax=docker/dockerfile:1

FROM node:22-alpine AS deps
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm install --omit=dev --no-audit --no-fund && npm cache clean --force

FROM node:22-alpine AS build
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY src ./src
COPY package*.json ./
RUN npm prune --omit=dev && npm cache clean --force

FROM node:22-alpine AS production
WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000
COPY --from=build /app/package*.json ./
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/src ./src
USER node
EXPOSE 3000
CMD ["node", "src/index.js"]
```

```text backend/.dockerignore
node_modules
npm-debug.log
.DS_Store
.git
.env
.env.*
coverage
```

```json backend/package.json
{
  "name": "storage-api",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js"
  },
  "engines": {
    "node": ">=22"
  },
  "dependencies": {
    "cors": "^2.8.5",
    "express": "^4.21.2",
    "pg": "^8.13.1"
  }
}
```

```javascript backend/src/index.js
import cors from 'cors';
import express from 'express';
import pg from 'pg';

const { Pool } = pg;
const SELECT_COLUMNS = 'id, name, value, created_at, updated_at';

const app = express();
const port = positiveInt(process.env.PORT, 3000);

const pool = new Pool({
  host: process.env.DB_HOST || 'localhost',
  port: positiveInt(process.env.DB_PORT, 5432),
  database: process.env.DB_NAME || 'storage',
  user: process.env.DB_USER || 'app',
  password: process.env.DB_PASSWORD || 'app_password',
  max: positiveInt(process.env.DB_POOL_SIZE, 10),
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});

app.use(
  cors({
    origin: parseCsv(process.env.CORS_ORIGIN) ?? true,
    methods: ['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
    allowedHeaders: ['Content-Type'],
  })
);
app.use(express.json({ limit: '100kb' }));

app.get('/api', (req, res) => {
  res.json({ service: 'storage-api', status: 'ok' });
});

app.get('/health', asyncHandler(async (req, res) => {
  await pool.query('SELECT 1');
  res.json({ service: 'storage-api', status: 'ok', database: 'connected' });
}));

app.get('/api/items', asyncHandler(async (req, res) => {
  const result = await pool.query(`
    SELECT ${SELECT_COLUMNS}
    FROM items
    ORDER BY created_at DESC, id DESC
  `);

  res.json(result.rows.map(serializeItem));
}));

app.post('/api/items', asyncHandler(async (req, res) => {
  const payload = parseCreatePayload(req);
  const result = await pool.query(
    `INSERT INTO items (name, value)
     VALUES ($1, $2)
     RETURNING ${SELECT_COLUMNS}`,
    [payload.name, payload.value]
  );

  res.status(201).json(serializeItem(result.rows[0]));
}));

app.get('/api/items/:id', asyncHandler(async (req, res) => {
  const id = parseId(req);
  const item = await findRawItem(id);

  if (!item) {
    throw httpError(404, 'Item not found');
  }

  res.json(serializeItem(item));
}));

app.patch('/api/items/:id', asyncHandler(async (req, res) => {
  const id = parseId(req);
  const existing = await findRawItem(id);

  if (!existing) {
    throw httpError(404, 'Item not found');
  }

  const updates = parseUpdatePayload(req);
  const assignments = [];
  const values = [];

  if (updates.name !== undefined) {
    values.push(updates.name);
    assignments.push(`name = $${values.length}`);
  }

  if (updates.value !== undefined) {
    values.push(updates.value);
    assignments.push(`value = $${values.length}`);
  }

  values.push(id);

  const result = await pool.query(
    `UPDATE items
     SET ${assignments.join(', ')}, updated_at = NOW()
     WHERE id = $${values.length}
     RETURNING ${SELECT_COLUMNS}`,
    values
  );

  res.json(serializeItem(result.rows[0]));
}));

app.delete('/api/items/:id', asyncHandler(async (req, res) => {
  const id = parseId(req);
  const existing = await findRawItem(id);

  if (!existing) {
    throw httpError(404, 'Item not found');
  }

  await pool.query('DELETE FROM items WHERE id = $1', [id]);
  res.status(204).end();
}));

app.use((req, res) => {
  res.status(404).json({ error: 'Not Found' });
});

app.use((error, req, res, next) => {
  const status = Number.isInteger(error.status) ? error.status : 500;
  const message = status === 500 ? 'Internal Server Error' : error.message;

  if (status === 500) {
    console.error(error);
  }

  res.status(status).json({ error: message });
});

async function main() {
  await ensureSchema();

  const server = app.listen(port, '0.0.0.0', () => {
    console.log(`Backend API listening on 0.0.0.0:${port}`);
  });

  server.on('error', (error) => {
    console.error(error);
    process.exit(1);
  });

  const shutdown = (signal) => {
    console.info(`${signal} received; shutting down`);

    server.close(() => {
      pool.end()
        .then(() => process.exit(0))
        .catch((error) => {
          console.error(error);
          process.exit(1);
        });
    });

    setTimeout(() => process.exit(1), 10_000).unref();
  };

  process.once('SIGINT', () => shutdown('SIGINT'));
  process.once('SIGTERM', () => shutdown('SIGTERM'));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

function asyncHandler(handler) {
  return (req, res, next) => {
    Promise.resolve(handler(req, res, next)).catch(next);
  };
}

function parseCreatePayload(req) {
  const body = req.body ?? {};
  const name = String(body.name ?? '').trim();

  if (!name) {
    throw httpError(400, 'name is required');
  }

  if (name.length > 255) {
    throw httpError(400, 'name must be 255 characters or fewer');
  }

  return {
    name,
    value: body.value == null ? null : String(body.value).slice(0, 5000),
  };
}

function parseUpdatePayload(req) {
  const body = req.body ?? {};
  const updates = {};

  if (hasOwn(body, 'name')) {
    const name = String(body.name ?? '').trim();

    if (!name) {
      throw httpError(400, 'name must not be empty');
    }

    if (name.length > 255) {
      throw httpError(400, 'name must be 255 characters or fewer');
    }

    updates.name = name;
  }

  if (hasOwn(body, 'value')) {
    updates.value = body.value == null ? null : String(body.value).slice(0, 5000);
  }

  if (Object.keys(updates).length === 0) {
    throw httpError(400, 'Provide name and/or value');
  }

  return updates;
}

function parseId(req) {
  const id = Number(req.params.id);

  if (!Number.isInteger(id) || id < 1) {
    throw httpError(400, 'id must be a positive integer');
  }

  return id;
}

async function findRawItem(id) {
  const result = await pool.query(
    `SELECT ${SELECT_COLUMNS}
     FROM items
     WHERE id = $1`,
    [id]
  );

  return result.rows[0] ?? null;
}

async function ensureSchema() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS items (
      id SERIAL PRIMARY KEY,
      name VARCHAR(255) NOT NULL,
      value TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `);

  await pool.query(
    'CREATE INDEX IF NOT EXISTS idx_items_created_at_desc ON items (created_at DESC)'
  );
}

function serializeItem(row) {
  return {
    id: row.id,
    name: row.name,
    value: row.value,
    created_at: row.created_at.toISOString(),
    updated_at: row.updated_at.toISOString(),
  };
}

function parseCsv(value) {
  if (!value) {
    return undefined;
  }

  const items = value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  return items.length > 0 ? items : undefined;
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function httpError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function positiveInt(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? Math.trunc(number) : fallback;
}
```

```dockerfile frontend/Dockerfile
# syntax=docker/dockerfile:1

FROM node:22-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund && npm cache clean --force

FROM node:22-alpine AS build
WORKDIR /app
ARG VITE_API_BASE_URL=http://localhost:3000/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build && npm cache clean --force

FROM nginx:1.27-alpine AS production
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
USER nginx
```

```text frontend/.dockerignore
node_modules
dist
npm-debug.log
.DS_Store
.git
.env
.env.*
```

```json frontend/package.json
{
  "name": "storage-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0 --port 4173"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "vite": "^5.4.11"
  }
}
```

```javascript frontend/vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
  },
});
```

```html frontend/index.html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Storage Microservices</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

```nginx frontend/nginx.conf
worker_processes auto;
error_log /tmp/nginx-error.log notice;
pid /tmp/nginx.pid;

events {
  worker_connections 1024;
}

http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;

  access_log /tmp/nginx-access.log;
  sendfile on;
  keepalive_timeout 65;

  server {
    listen 8080;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
      try_files $uri $uri/ /index.html;
    }

    location = /healthz {
      access_log off;
      default_type text/plain;
      return 200 'ok\n';
    }
  }
}
```

```javascript frontend/src/main.jsx
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './App.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```javascript frontend/src/api.js
export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000/api'
).replace(/\/$/, '');

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
  });

  const text = await response.text();
  const data = text ? parseJson(text) : undefined;

  if (!response.ok) {
    throw new Error(data?.message || data?.error || response.statusText);
  }

  return data;
}

function parseJson(text) {
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

export function listItems() {
  return request('/items', { cache: 'no-store' });
}

export function createItem(body) {
  return request('/items', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function updateItem(id, body) {
  return request(`/items/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export function deleteItem(id) {
  return request(`/items/${id}`, {
    method: 'DELETE',
  });
}
```

```jsx frontend/src/App.jsx
import { useEffect, useState } from 'react';
import {
  API_BASE_URL,
  createItem,
  deleteItem,
  listItems,
  updateItem,
} from './api.js';
import './App.css';

export default function App() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState('');
  const [value, setValue] = useState('');
  const [draft, setDraft] = useState({ id: null, value: '' });
  const [status, setStatus] = useState('Loading items…');
  const [error, setError] = useState('');

  async function refreshItems() {
    setStatus('Loading items…');
    setError('');

    try {
      const data = await listItems();
      setItems(data);
      setStatus(
        data.length === 0
          ? 'No items stored yet.'
          : `${data.length} item${data.length === 1 ? '' : 's'} loaded.`
      );
    } catch (err) {
      setError(errorMessage(err));
      setStatus('Unable to load items.');
    }
  }

  useEffect(() => {
    refreshItems();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const cleanName = name.trim();

    if (!cleanName) {
      setError('Item name is required.');
      return;
    }

    try {
      const item = await createItem({
        name: cleanName,
        value: value.trim() || null,
      });

      setItems((current) => [item, ...current]);
      setName('');
      setValue('');
      setError('');
      setStatus('Item created.');
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  function startEdit(item) {
    setDraft({ id: item.id, value: item.value ?? '' });
  }

  async function saveDraft() {
    if (!draft.id) {
      return;
    }

    try {
      const item = await updateItem(draft.id, { value: draft.value });
      setItems((current) =>
        current.map((existing) => (existing.id === item.id ? item : existing))
      );
      setDraft({ id: null, value: '' });
      setError('');
      setStatus('Item updated.');
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function handleDelete(id) {
    try {
      await deleteItem(id);
      setItems((current) => current.filter((item) => item.id !== id));

      if (draft.id === id) {
        setDraft({ id: null, value: '' });
      }

      setError('');
      setStatus('Item deleted.');
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Microservices data storage</p>
        <h1>Full-stack item storage</h1>
        <p className="lede">
          A decoupled React UI, Express API, and PostgreSQL service orchestrated
          with Docker Compose.
        </p>
        <div className="architecture" aria-label="Service flow">
          <span>Frontend</span>
          <span>→</span>
          <span>Backend API</span>
          <span>→</span>
          <span>Database</span>
        </div>
      </section>

      <section className="layout">
        <form className="panel form-panel" onSubmit={handleSubmit}>
          <h2>Create item</h2>

          <div className="field">
            <label htmlFor="item-name">Name</label>
            <input
              id="item-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Customer record"
              maxLength={255}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="item-value">Value</label>
            <textarea
              id="item-value"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="Optional notes"
              rows={5}
              maxLength={5000}
            />
          </div>

          <button type="submit">Create item</button>

          <p className="hint">
            API endpoint: <code>{API_BASE_URL}</code>
          </p>
        </form>

        <section className="panel items-panel" aria-busy={status.startsWith('Loading')}>
          <div className="toolbar">
            <div>
              <h2>Stored items</h2>
              <p className="status" role="status" aria-live="polite">
                {status}
              </p>
            </div>
            <button type="button" className="secondary" onClick={refreshItems}>
              Refresh
            </button>
          </div>

          {error ? <div className="error-banner" role="alert">{error}</div> : null}

          <ul className="items-list">
            {items.length === 0 ? (
              <li className="empty-state">
                No items yet. Create one to test the storage pipeline.
              </li>
            ) : (
              items.map((item) => (
                <li className="item-card" key={item.id}>
                  <div className="item-main">
                    <div>
                      <h3>{item.name}</h3>
                      <p>
                        {item.value || (
                          <span className="muted">No value stored</span>
                        )}
                      </p>
                    </div>
                    <div className="item-meta">
                      <time dateTime={item.created_at}>
                        Created {new Date(item.created_at).toLocaleString()}
                      </time>
                      <time dateTime={item.updated_at}>
                        Updated {new Date(item.updated_at).toLocaleString()}
                      </time>
                    </div>
                  </div>

                  {draft.id === item.id ? (
                    <div className="edit-box">
                      <label htmlFor={`value-${item.id}`}>Value</label>
                      <textarea
                        id={`value-${item.id}`}
                        value={draft.value}
                        onChange={(event) =>
                          setDraft({ ...draft, value: event.target.value })
                        }
                        rows={4}
                        maxLength={5000}
                      />
                      <div className="actions">
                        <button type="button" onClick={saveDraft}>
                          Save
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => setDraft({ id: null, value: '' })}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="actions">
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => startEdit(item)}
                      >
                        Edit value
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => handleDelete(item.id)}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </li>
              ))
            )}
          </ul>
        </section>
      </section>
    </main>
  );
}

function errorMessage(error) {
  return error instanceof Error && error.message ? error.message : 'Request failed.';
}
```

```css frontend/src/App.css
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #0f172a;
  color: #e5e7eb;
}

* {
  box-sizing: border-box;
}

html,
body,
#root {
  min-height: 100%;
}

body {
  margin: 0;
  min-width: 320px;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.25), transparent 32rem),
    radial-gradient(circle at bottom right, rgba(168, 85, 247, 0.22), transparent 28rem),
    #0f172a;
}

button,
input,
textarea {
  font: inherit;
}

button {
  border: 0;
  border-radius: 14px;
  background: #38bdf8;
  color: #082f49;
  cursor: pointer;
  font-weight: 700;
  padding: 12px 16px;
  transition: transform 160ms ease, filter 160ms ease;
}

button:hover {
  filter: brightness(1.05);
  transform: translateY(-1px);
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible {
  outline: 3px solid rgba(56, 189, 248, 0.35);
  outline-offset: 2px;
}

button.secondary {
  background: rgba(148, 163, 184, 0.16);
  border: 1px solid rgba(148, 163, 184, 0.24);
  color: #e5e7eb;
}

button.danger {
  background: rgba(248, 113, 113, 0.16);
  border: 1px solid rgba(248, 113, 113, 0.32);
  color: #fecaca;
}

.app-shell {
  margin: 0 auto;
  padding: 48px 0;
  width: min(1120px, calc(100% - 32px));
}

.hero,
.panel {
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.74);
  border-radius: 28px;
  box-shadow: 0 24px 80px rgba(2, 6, 23, 0.35);
  backdrop-filter: blur(16px);
}

.hero {
  padding: 32px;
}

.panel {
  padding: 24px;
}

.eyebrow,
.lede,
.hint,
.status,
.item-meta,
.empty-state {
  color: #94a3b8;
}

.eyebrow {
  margin: 0 0 10px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.78rem;
  font-weight: 800;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 12px;
  font-size: clamp(2.5rem, 7vw, 5rem);
  line-height: 0.95;
  letter-spacing: -0.06em;
}

h2 {
  margin-bottom: 18px;
  font-size: 1.35rem;
}

h3 {
  margin-bottom: 8px;
  color: #f8fafc;
}

.lede {
  max-width: 720px;
  line-height: 1.7;
  font-size: 1.05rem;
}

.architecture {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 24px;
}

.architecture span {
  border: 1px solid rgba(56, 189, 248, 0.28);
  border-radius: 999px;
  background: rgba(56, 189, 248, 0.1);
  color: #bae6fd;
  padding: 8px 12px;
  font-weight: 700;
}

.layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) minmax(0, 1fr);
  gap: 24px;
  margin-top: 24px;
}

.form-panel {
  position: sticky;
  top: 24px;
  align-self: start;
}

.field {
  margin-bottom: 18px;
}

label {
  display: block;
  margin-bottom: 8px;
  color: #cbd5e1;
  font-weight: 700;
}

input,
textarea {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 14px;
  background: rgba(2, 6, 23, 0.42);
  color: #e5e7eb;
  padding: 12px 14px;
}

textarea {
  min-height: 110px;
  resize: vertical;
}

input::placeholder,
textarea::placeholder {
  color: #64748b;
}

input:focus,
textarea:focus {
  border-color: #38bdf8;
  box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.14);
  outline: none;
}

.hint {
  margin: 20px 0 0;
  font-size: 0.9rem;
}

code {
  color: #bae6fd;
}

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.status {
  margin-bottom: 0;
}

.error-banner {
  margin-top: 16px;
  border: 1px solid rgba(248, 113, 113, 0.32);
  border-radius: 14px;
  background: rgba(248, 113, 113, 0.14);
  color: #fecaca;
  padding: 12px 14px;
}

.items-list {
  display: grid;
  gap: 16px;
  list-style: none;
  margin: 20px 0 0;
  padding: 0;
}

.item-card,
.empty-state {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.48);
  padding: 18px;
}

.item-main {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.item-main p {
  margin-bottom: 0;
  color: #cbd5e1;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.item-meta {
  display: grid;
  gap: 4px;
  flex: 0 0 auto;
  font-size: 0.84rem;
  text-align: right;
}

.muted {
  color: #94a3b8;
  font-style: italic;
}

.edit-box {
  margin-top: 16px;
}

.edit-box textarea {
  min-height: 90px;
  margin-bottom: 12px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.empty-state {
  color: #94a3b8;
  border-style: dashed;
}

@media (max-width: 860px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .form-panel {
    position: static;
  }
}

@media (max-width: 640px) {
  .app-shell {
    padding: 24px 0;
    width: min(100% - 20px, 1120px);
  }

  .hero,
  .panel {
    border-radius: 22px;
    padding: 20px;
  }

  .item-main,
  .toolbar {
    flex-direction: column;
  }

  .item-meta {
    text-align: left;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
  }

  button:hover {
    transform: none;
  }
}
```

```sql database/init.sql
CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  value TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_items_created_at_desc ON items (created_at DESC);
```

# Checker Review
**Verdict: Pass, with minor warnings.**

| Spec item | Review |
|---|---|
| **Multi-stage builds** | **Yes.** Both custom services use multi-stage Dockerfiles: backend has `deps → build → production`; frontend has `deps → build → production`. |
| **Minimal images** | **Mostly yes.** Final images use Alpine-based images: `node:22-alpine` and `nginx:1.27-alpine`; database uses `postgres:16-alpine`. No dev-dependencies or build tools are copied into final production stages. |
| **Single `docker-compose.yml`** | **Yes.** One root-level `docker-compose.yml` defines all three services: `frontend`, `backend`, and `database`, with networks, volume, healthchecks, and dependency ordering. |

**Warnings / recommendations:**

1. `node:22-alpine` is lightweight but not the absolute smallest possible. If “absolute smallest” is interpreted strictly, consider a Node distroless/static final image for the backend.
2. Frontend final stage relies on the inherited `nginx` default `CMD`. Add an explicit command for clarity:

   ```dockerfile
   CMD ["nginx", "-g", "daemon off;"]
   ```

3. Frontend API URL is hardcoded to `http://localhost:3000/api`, which works for local browser access but may not work from remote/prod environments.
4. Modern Docker Compose commonly uses `docker compose up --build`; `docker-compose` is legacy but still valid if installed.