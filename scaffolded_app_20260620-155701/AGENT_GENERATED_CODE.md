# Maker Output
```yaml filename="docker-compose.yml"
services:
  database:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: data_storage
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: apppassword
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d data_storage"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - data-storage-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      NODE_ENV: production
      PORT: "3000"
      DB_HOST: database
      DB_PORT: "5432"
      DB_NAME: data_storage
      DB_USER: appuser
      DB_PASSWORD: apppassword
      DB_POOL_MAX: "10"
    depends_on:
      database:
        condition: service_healthy
    expose:
      - "3000"
    healthcheck:
      test:
        [
          "CMD",
          "/nodejs/bin/node",
          "-e",
          "require('http').get('http://127.0.0.1:3000/health', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"
        ]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
    networks:
      - data-storage-network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      args:
        VITE_API_BASE_URL: /api
    restart: unless-stopped
    environment:
      VITE_API_BASE_URL: /api
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 5s
    networks:
      - data-storage-network

networks:
  data-storage-network:
    driver: bridge

volumes:
  postgres_data:
```

```dockerignore filename="frontend/.dockerignore"
node_modules
dist
npm-debug.log
Dockerfile
.dockerignore
.git
.gitignore
.env
.env.*
```

```dockerfile filename="frontend/Dockerfile"
# syntax=docker/dockerfile:1

FROM node:22-alpine AS build

WORKDIR /app

ENV NODE_ENV=development
ENV npm_config_audit=false
ENV npm_config_fund=false

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY package.json ./
RUN npm install --include=dev && npm cache clean --force

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS production

COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf

RUN rm -rf /var/cache/nginx \
    && mkdir -p /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp \
    && chown -R nginx:nginx /usr/share/nginx/html /tmp/client_temp /tmp/proxy_temp /tmp/fastcgi_temp /tmp/uwsgi_temp /tmp/scgi_temp

USER nginx

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
```

```html filename="frontend/index.html"
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Storage</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```nginx filename="frontend/nginx.conf"
worker_processes auto;
pid /tmp/nginx.pid;

events {
  worker_connections 1024;
}

http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;

  sendfile on;
  server_tokens off;

  error_log /dev/stderr info;
  access_log /dev/stdout;

  client_max_body_size 100k;
  client_body_temp_path /tmp/client_temp;
  proxy_temp_path /tmp/proxy_temp;
  fastcgi_temp_path /tmp/fastcgi_temp;
  uwsgi_temp_path /tmp/uwsgi_temp;
  scgi_temp_path /tmp/scgi_temp;

  server {
    listen 8080;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location = /healthz {
      default_type text/plain;
      access_log off;
      return 200 "ok\n";
    }

    location /api/ {
      proxy_pass http://backend:3000/;
      proxy_http_version 1.1;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_set_header Connection "";
      proxy_connect_timeout 5s;
      proxy_send_timeout 60s;
      proxy_read_timeout 60s;
    }

    location / {
      try_files $uri $uri/ /index.html;
    }
  }
}
```

```json filename="frontend/package.json"
{
  "name": "data-storage-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "dependencies": {
    "@vitejs/plugin-react": "4.2.1",
    "react": "18.2.0",
    "react-dom": "18.2.0"
  },
  "devDependencies": {
    "@types/react": "18.2.79",
    "@types/react-dom": "18.2.25",
    "typescript": "5.4.5",
    "vite": "5.2.10"
  },
  "engines": {
    "node": ">=18"
  }
}
```

```json filename="frontend/tsconfig.json"
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2020"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
```

```typescript filename="frontend/vite.config.ts"
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': 'http://localhost:3000'
    }
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    sourcemap: false
  }
});
```

```tsx filename="frontend/src/App.tsx"
import { FormEvent, useEffect, useState } from 'react';
import type { Item, ItemInput } from './types';

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL && import.meta.env.VITE_API_BASE_URL.length > 0
    ? import.meta.env.VITE_API_BASE_URL
    : '/api'
).replace(/\/$/, '');

type Message = {
  type: 'success' | 'error';
  text: string;
};

const emptyForm = {
  title: '',
  description: '',
  metadataText: ''
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  const text = await response.text();
  let payload: unknown = {};

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = {
        error: text.trim() || `Request failed with status ${response.status}`
      };
    }
  }

  if (!response.ok) {
    const errorText =
      typeof payload === 'object' && payload !== null && 'error' in payload
        ? String((payload as { error: unknown }).error)
        : `Request failed with status ${response.status}`;

    throw new Error(errorText);
  }

  return payload as T;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value));
}

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<Message | null>(null);

  const loadItems = async (): Promise<void> => {
    setLoading(true);

    try {
      const data = await request<Item[]>('/items');
      setItems(data);
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Failed to load items'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadItems();
  }, []);

  const updateForm = (field: keyof typeof form, value: string): void => {
    setForm((current) => ({
      ...current,
      [field]: value
    }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setSaving(true);
    setMessage(null);

    try {
      const metadataText = form.metadataText.trim();
      let metadata: unknown = {};

      if (metadataText) {
        metadata = JSON.parse(metadataText);
      }

      if (typeof metadata !== 'object' || metadata === null || Array.isArray(metadata)) {
        throw new Error('Metadata must be a JSON object.');
      }

      const payload: ItemInput = {
        title: form.title.trim(),
        description: form.description.trim(),
        metadata: metadata as Record<string, unknown>
      };

      const created = await request<Item>('/items', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      setItems((current) => [created, ...current]);
      setForm({ ...emptyForm });
      setMessage({ type: 'success', text: 'Item saved.' });
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Failed to save item'
      });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number): Promise<void> => {
    try {
      await request<Item>(`/items/${id}`, {
        method: 'DELETE'
      });

      setItems((current) => current.filter((item) => item.id !== id));
      setMessage({ type: 'success', text: 'Item deleted.' });
    } catch (error) {
      setMessage({
        type: 'error',
        text: error instanceof Error ? error.message : 'Failed to delete item'
      });
    }
  };

  return (
    <main className="app-shell" aria-busy={loading || saving}>
      <section className="hero">
        <div>
          <p className="eyebrow">Microservices Data Storage</p>
          <h1>Store and manage structured records</h1>
          <p className="lede">
            This frontend talks to the backend API through an isolated reverse proxy. The backend
            persists every item in PostgreSQL.
          </p>
        </div>

        <form className="storage-form" onSubmit={handleSubmit}>
          <div className="form-grid">
            <label htmlFor="title">
              Title
              <input
                id="title"
                value={form.title}
                onChange={(event) => updateForm('title', event.target.value)}
                disabled={saving || loading}
                required
              />
            </label>

            <label htmlFor="description">
              Description
              <textarea
                id="description"
                value={form.description}
                onChange={(event) => updateForm('description', event.target.value)}
                disabled={saving || loading}
                rows={3}
              />
            </label>

            <label htmlFor="metadata">
              Metadata JSON
              <textarea
                id="metadata"
                value={form.metadataText}
                onChange={(event) => updateForm('metadataText', event.target.value)}
                disabled={saving || loading}
                rows={5}
                placeholder='{"source":"frontend","priority":1}'
              />
            </label>
          </div>

          <button type="submit" disabled={saving || loading}>
            {saving ? 'Saving...' : 'Save item'}
          </button>
        </form>
      </section>

      <section className="items-panel">
        <div className="section-heading">
          <h2>Stored items</h2>
          {message && (
            <div className={`message ${message.type}`} role="status" aria-live="polite">
              {message.text}
            </div>
          )}
        </div>

        {loading ? (
          <p className="muted">Loading items...</p>
        ) : items.length === 0 ? (
          <p className="muted">No items stored yet.</p>
        ) : (
          <ul className="items-list">
            {items.map((item) => (
              <li className="item-card" key={item.id}>
                <div className="item-header">
                  <div>
                    <span className="item-id">#{item.id}</span>
                    <h3>{item.title}</h3>
                  </div>
                  <button
                    className="danger-button"
                    type="button"
                    onClick={() => void handleDelete(item.id)}
                    disabled={saving}
                  >
                    Delete
                  </button>
                </div>

                <p className="item-description">{item.description || 'No description'}</p>

                <div className="metadata-block">
                  <span>Metadata</span>
                  <pre>{JSON.stringify(item.metadata ?? {}, null, 2)}</pre>
                </div>

                <div className="timestamps">
                  <span>Created: {formatDate(item.created_at)}</span>
                  <span>Updated: {formatDate(item.updated_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
```

```typescript filename="frontend/src/main.tsx"
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```css filename="frontend/src/styles.css"
:root {
  color: #172033;
  background: #f5f7fb;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

button,
input,
textarea {
  font: inherit;
}

button {
  border: 0;
  border-radius: 12px;
  padding: 0.85rem 1rem;
  color: #ffffff;
  background: #2563eb;
  cursor: pointer;
  font-weight: 700;
  transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
  box-shadow: 0 10px 25px rgba(37, 99, 235, 0.25);
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #1d4ed8;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

input,
textarea {
  width: 100%;
  margin-top: 0.45rem;
  border: 1px solid #d8dee9;
  border-radius: 12px;
  padding: 0.8rem 0.9rem;
  color: #172033;
  background: #ffffff;
  outline: none;
}

input:focus,
textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

textarea {
  resize: vertical;
}

.app-shell {
  width: min(1180px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0;
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(360px, 1.05fr);
  gap: 28px;
  align-items: start;
  margin-bottom: 28px;
}

.eyebrow,
.lede,
.muted,
.timestamps {
  color: #64748b;
}

.eyebrow {
  margin: 0 0 0.6rem;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 0.85rem;
  font-size: clamp(2.2rem, 5vw, 4.4rem);
  line-height: 0.95;
  letter-spacing: -0.06em;
}

h2 {
  margin-bottom: 0;
  font-size: 1.45rem;
  letter-spacing: -0.03em;
}

h3 {
  margin: 0.25rem 0 0;
  font-size: 1.15rem;
}

.lede {
  max-width: 58ch;
  line-height: 1.7;
}

.storage-form,
.items-panel {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 28px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18px);
}

.form-grid {
  display: grid;
  gap: 18px;
}

label {
  display: block;
  color: #334155;
  font-size: 0.9rem;
  font-weight: 800;
}

.section-heading {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.message {
  border-radius: 999px;
  padding: 0.5rem 0.85rem;
  font-size: 0.86rem;
  font-weight: 800;
}

.message.success {
  color: #166534;
  background: #dcfce7;
}

.message.error {
  color: #991b1b;
  background: #fee2e2;
}

.items-list {
  display: grid;
  gap: 16px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.item-card {
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  padding: 18px;
  background: #ffffff;
}

.item-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
}

.item-id {
  color: #2563eb;
  font-size: 0.8rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.item-description {
  color: #475569;
  line-height: 1.6;
}

.danger-button {
  flex: 0 0 auto;
  padding: 0.65rem 0.85rem;
  color: #991b1b;
  background: #fee2e2;
  box-shadow: none;
}

.danger-button:hover:not(:disabled) {
  background: #fecaca;
}

.metadata-block {
  margin-top: 14px;
}

.metadata-block span {
  display: inline-block;
  margin-bottom: 0.45rem;
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

pre {
  overflow: auto;
  margin: 0;
  border-radius: 14px;
  padding: 14px;
  color: #dbeafe;
  background: #0f172a;
  font-size: 0.84rem;
  line-height: 1.5;
}

.timestamps {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin-top: 14px;
  font-size: 0.82rem;
}

@media (max-width: 860px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .section-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

```typescript filename="frontend/src/types.ts"
export type Item = {
  id: number;
  title: string;
  description: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type ItemInput = {
  title: string;
  description: string;
  metadata: Record<string, unknown>;
};
```

```dockerignore filename="backend/.dockerignore"
node_modules
dist
npm-debug.log
Dockerfile
.dockerignore
.git
.gitignore
.env
.env.*
```

```dockerfile filename="backend/Dockerfile"
# syntax=docker/dockerfile:1

FROM node:22-alpine AS build

WORKDIR /app

ENV NODE_ENV=development
ENV npm_config_audit=false
ENV npm_config_fund=false

COPY package.json ./
RUN npm install --include=dev && npm cache clean --force

COPY tsconfig.json ./
COPY src ./src
RUN npm run build
RUN npm prune --omit=dev && npm cache clean --force

FROM gcr.io/distroless/nodejs22-debian12 AS production

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build --chown=nonroot:nonroot /app/dist ./dist
COPY --from=build --chown=nonroot:nonroot /app/node_modules ./node_modules

USER nonroot

EXPOSE 3000

CMD ["dist/server.js"]
```

```json filename="backend/package.json"
{
  "name": "data-storage-backend",
  "version": "1.0.0",
  "private": true,
  "main": "dist/server.js",
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "start": "node dist/server.js",
    "dev": "tsx watch src/server.ts"
  },
  "dependencies": {
    "express": "4.18.3",
    "pg": "8.11.5",
    "zod": "3.23.8"
  },
  "devDependencies": {
    "@types/express": "4.17.21",
    "@types/node": "20.12.7",
    "@types/pg": "8.11.6",
    "tsx": "4.7.3",
    "typescript": "5.4.5"
  },
  "engines": {
    "node": ">=22"
  }
}
```

```json filename="backend/tsconfig.json"
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "Node",
    "lib": ["ES2022"],
    "rootDir": "src",
    "outDir": "dist",
    "strict": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "types": ["node"]
  },
  "include": ["src/**/*.ts"]
}
```

```typescript filename="backend/src/config.ts"
const toPositiveInteger = (value: string | undefined, fallback: number): number => {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
};

export const config = {
  port: toPositiveInteger(process.env.PORT, 3000),
  db: {
    host: process.env.DB_HOST ?? 'database',
    port: toPositiveInteger(process.env.DB_PORT, 5432),
    database: process.env.DB_NAME ?? 'data_storage',
    user: process.env.DB_USER ?? 'appuser',
    password: process.env.DB_PASSWORD ?? 'apppassword',
    max: toPositiveInteger(process.env.DB_POOL_MAX, 10)
  }
};
```

```typescript filename="backend/src/db.ts"
import { Pool } from 'pg';
import { config } from './config';

export const pool = new Pool({
  host: config.db.host,
  port: config.db.port,
  database: config.db.database,
  user: config.db.user,
  password: config.db.password,
  max: config.db.max,
  connectionTimeoutMillis: 5000
});

export async function ensureSchema(): Promise<void> {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS items (
      id BIGSERIAL PRIMARY KEY,
      title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 255),
      description TEXT NOT NULL DEFAULT '',
      metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_items_created_at ON items (created_at DESC, id DESC);
  `);
}
```

```typescript filename="backend/src/server.ts"
import express, { NextFunction, Request, Response } from 'express';
import { z } from 'zod';
import { config } from './config';
import { ensureSchema, pool } from './db';

type ItemRow = {
  id: number;
  title: string;
  description: string;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

class HttpError extends Error {
  statusCode: number;

  constructor(statusCode: number, message: string) {
    super(message);
    this.name = 'HttpError';
    this.statusCode = statusCode;
  }
}

const createItemSchema = z.object({
  title: z.string().trim().min(1).max(255),
  description: z.string().trim().max(5000).optional().default(''),
  metadata: z.record(z.unknown()).optional().default({})
});

const updateItemSchema = createItemSchema.partial();
const selectColumns = 'id, title, description, metadata, created_at, updated_at';

function parseId(value: string): number {
  const id = Number(value);

  if (!Number.isInteger(id) || id <= 0) {
    throw new HttpError(400, 'Invalid item id');
  }

  return id;
}

async function main(): Promise<void> {
  await waitForDatabase();

  const app = express();

  app.disable('x-powered-by');
  app.use(express.json({ limit: '100kb' }));

  app.get('/health', async (_req: Request, res: Response) => {
    try {
      await pool.query('SELECT 1');
      res.json({ status: 'ok' });
    } catch (error) {
      console.error(error);
      res.status(503).json({ status: 'error' });
    }
  });

  app.get('/items', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const result = await pool.query<ItemRow>(
        `SELECT ${selectColumns} FROM items ORDER BY created_at DESC, id DESC`
      );
      res.json(result.rows);
    } catch (error) {
      next(error);
    }
  });

  app.post('/items', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const item = createItemSchema.parse(req.body);
      const result = await pool.query<ItemRow>(
        `INSERT INTO items (title, description, metadata)
         VALUES ($1, $2, $3::jsonb)
         RETURNING ${selectColumns}`,
        [item.title, item.description, item.metadata]
      );

      res.status(201).json(result.rows[0]);
    } catch (error) {
      next(error);
    }
  });

  app.get('/items/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = parseId(req.params.id);
      const result = await pool.query<ItemRow>(
        `SELECT ${selectColumns} FROM items WHERE id = $1`,
        [id]
      );

      if (result.rowCount === 0) {
        throw new HttpError(404, 'Item not found');
      }

      res.json(result.rows[0]);
    } catch (error) {
      next(error);
    }
  });

  app.patch('/items/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = parseId(req.params.id);
      const updates = updateItemSchema.parse(req.body);
      const result = await pool.query<ItemRow>(
        `UPDATE items
         SET title = COALESCE($2, title),
             description = COALESCE($3, description),
             metadata = COALESCE($4::jsonb, metadata),
             updated_at = NOW()
         WHERE id = $1
         RETURNING ${selectColumns}`,
        [id, updates.title ?? null, updates.description ?? null, updates.metadata ?? null]
      );

      if (result.rowCount === 0) {
        throw new HttpError(404, 'Item not found');
      }

      res.json(result.rows[0]);
    } catch (error) {
      next(error);
    }
  });

  app.delete('/items/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = parseId(req.params.id);
      const result = await pool.query<ItemRow>(
        `DELETE FROM items WHERE id = $1 RETURNING ${selectColumns}`,
        [id]
      );

      if (result.rowCount === 0) {
        throw new HttpError(404, 'Item not found');
      }

      res.json(result.rows[0]);
    } catch (error) {
      next(error);
    }
  });

  app.use((error: unknown, _req: Request, res: Response, _next: NextFunction) => {
    if (error instanceof HttpError) {
      res.status(error.statusCode).json({ error: error.message });
      return;
    }

    if (error instanceof z.ZodError) {
      res.status(400).json({
        error: 'Validation failed',
        details: error.issues.map((issue) => ({
          path: issue.path.join('.'),
          message: issue.message
        }))
      });
      return;
    }

    if (error instanceof SyntaxError && 'body' in error) {
      res.status(400).json({ error: 'Invalid JSON payload' });
      return;
    }

    const maybeError = error as { statusCode?: unknown; status?: unknown; message?: unknown };
    const statusCode = Number(maybeError.statusCode ?? maybeError.status);

    if (Number.isInteger(statusCode) && statusCode >= 400 && statusCode < 600) {
      res.status(statusCode).json({ error: maybeError.message ?? 'Request failed' });
      return;
    }

    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  });

  const server = app.listen(config.port, () => {
    console.log(`Backend listening on port ${config.port}`);
  });

  const shutdown = (): void => {
    console.log('Shutting down backend');

    server.close(() => {
      pool
        .end()
        .then(() => process.exit(0))
        .catch(() => process.exit(1));
    });

    setTimeout(() => {
      console.error('Forced shutdown after timeout');
      process.exit(1);
    }, 10_000).unref();
  };

  process.on('SIGTERM', () => {
    void shutdown();
  });

  process.on('SIGINT', () => {
    void shutdown();
  });
}

async function waitForDatabase(): Promise<void> {
  let attempt = 1;

  while (true) {
    try {
      await pool.query('SELECT 1');
      await ensureSchema();
      return;
    } catch (error) {
      if (attempt >= 30) {
        throw error;
      }

      console.warn(
        `Database unavailable (attempt ${attempt}/30):`,
        error instanceof Error ? error.message : String(error)
      );

      await new Promise((resolve) => setTimeout(resolve, Math.min(attempt * 1000, 5000)));
      attempt += 1;
    }
  }
}

void main().catch((error: unknown) => {
  console.error('Failed to start backend:', error instanceof Error ? error.message : String(error));
  void pool.end().finally(() => process.exit(1));
});
```

# Checker Review
## Brief Review

**Overall: Compliant with the Docker/infrastructure requirements, with minor caveats.**

### Multi-Stage Builds
✅ **Yes.** Both custom microservices use Docker multi-stage builds:

- **Frontend:** `node:22-alpine` build stage → `nginx:1.27-alpine` production stage.
- **Backend:** `node:22-alpine` build stage → `gcr.io/distroless/nodejs22-debian12` production stage.

### Minimal Images
✅ **Mostly yes.**

- **Backend** uses a **distroless** production image and prunes dev dependencies before copying `node_modules`.
- **Frontend** uses **nginx:alpine**, which is lightweight and matches the allowed `alpine` guidance.
- **Database** uses `postgres:16-alpine`.

No build-time dependencies appear to be copied into final production stages.

### Single `docker-compose.yml`
✅ **Yes.** There is a single root-level `docker-compose.yml` that defines:

- Frontend
- Backend
- Database
- Bridge network
- PostgreSQL volume
- Health checks
- Service dependencies

It should start with:

```bash
docker-compose up --build
```

## Warnings

1. **Frontend image is not the absolute smallest possible.**  
   `nginx:1.27-alpine` is acceptable, but if “absolute smallest” is interpreted strictly, a distroless/static web server image would be smaller.

2. **Compose health condition compatibility.**  
   `depends_on.condition: service_healthy` requires modern Docker Compose / Compose v2. Older `docker-compose` v1 versions may need a `version: "2.4"` declaration or equivalent compatibility adjustment.

3. **No lockfiles shown.**  
   `package-lock.json` files are not included. Adding them would improve build reproducibility.