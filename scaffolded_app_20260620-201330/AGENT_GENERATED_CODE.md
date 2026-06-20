# Maker Output
```yaml title="docker-compose.yml"
version: "3.9"

services:
  database:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: storage_db
      POSTGRES_USER: storage_user
      POSTGRES_PASSWORD: storage_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U storage_user -d storage_db"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - storage-net

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    image: storage-backend:local
    restart: unless-stopped
    environment:
      NODE_ENV: production
      PORT: "3000"
      DATABASE_URL: postgres://storage_user:storage_password@database:5432/storage_db
      CORS_ORIGIN: "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173"
    ports:
      - "3000:3000"
    depends_on:
      database:
        condition: service_healthy
    healthcheck:
      test:
        - CMD-SHELL
        - >
          node -e "fetch('http://127.0.0.1:3000/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 15s
    networks:
      - storage-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    image: storage-frontend:local
    restart: unless-stopped
    environment:
      VITE_API_BASE_URL: /api
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/health >/dev/null 2>&1 || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - storage-net

networks:
  storage-net:
    driver: bridge

volumes:
  postgres_data:
```

```dockerfile title="backend/Dockerfile"
FROM node:20-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm install --omit=dev --no-audit --no-fund


FROM node:20-alpine AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY package*.json ./
COPY src ./src

RUN npm run build


FROM node:20-alpine AS production

ENV NODE_ENV=production \
    PORT=3000

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./

USER node

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/health').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "dist/server.js"]
```

```json title="backend/package.json"
{
  "name": "storage-backend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "main": "dist/server.js",
  "scripts": {
    "dev": "node --watch src/server.js",
    "build": "mkdir -p dist && cp -R src/. dist/",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "cors": "^2.8.5",
    "express": "^4.21.2",
    "pg": "^8.13.1"
  }
}
```

```sql title="backend/db/init.sql"
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL CHECK (char_length(title) <= 255),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_records_created_at_desc ON records (created_at DESC);
```

```js title="backend/src/db.js"
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: Number(process.env.PGPOOL_MAX || 10),
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});

pool.on("error", (error) => {
  console.error("Unexpected database connection error", error);
});

export async function dbQuery(text, values = []) {
  return pool.query(text, values);
}

export async function closeDatabase() {
  await pool.end();
}
```

```js title="backend/src/server.js"
import cors from "cors";
import express from "express";
import { closeDatabase, dbQuery } from "./db.js";

const SELECT_COLUMNS = "id, title, payload, created_at, updated_at";
const app = express();
const port = Number(process.env.PORT || 3000);

const allowedOrigins = (process.env.CORS_ORIGIN || "http://localhost:8080")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const corsOptions = {
  origin(origin, callback) {
    if (!origin) {
      return callback(null, true);
    }

    const isAllowed =
      allowedOrigins.includes("*") ||
      allowedOrigins.includes(origin) ||
      /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);

    callback(null, isAllowed);
  },
};

app.disable("x-powered-by");
app.use(cors(corsOptions));
app.use(express.json({ limit: "1mb" }));

app.get("/health", async (_req, res) => {
  try {
    await dbQuery("SELECT 1");
    res.json({ status: "ok" });
  } catch (error) {
    res.status(503).json({ status: "error", error: "database unavailable" });
  }
});

app.get("/api/records", async (_req, res, next) => {
  try {
    const result = await dbQuery(
      `SELECT ${SELECT_COLUMNS}
       FROM records
       ORDER BY created_at DESC
       LIMIT 100`
    );

    res.json(result.rows);
  } catch (error) {
    next(error);
  }
});

app.post("/api/records", async (req, res, next) => {
  try {
    const title = String(req.body.title ?? "Untitled").trim().slice(0, 255) || "Untitled";
    const payload = req.body.payload ?? {};

    const result = await dbQuery(
      `INSERT INTO records (title, payload)
       VALUES ($1, $2)
       RETURNING ${SELECT_COLUMNS}`,
      [title, payload]
    );

    res.status(201).json(result.rows[0]);
  } catch (error) {
    next(error);
  }
});

app.get("/api/records/:id", async (req, res, next) => {
  try {
    const result = await dbQuery(
      `SELECT ${SELECT_COLUMNS}
       FROM records
       WHERE id = $1`,
      [req.params.id]
    );

    if (result.rowCount === 0) {
      res.status(404).json({ error: "Record not found" });
      return;
    }

    res.json(result.rows[0]);
  } catch (error) {
    next(error);
  }
});

app.patch("/api/records/:id", async (req, res, next) => {
  try {
    const title =
      req.body.title === undefined
        ? undefined
        : String(req.body.title).trim().slice(0, 255) || undefined;

    const payload = Object.prototype.hasOwnProperty.call(req.body, "payload")
      ? req.body.payload
      : undefined;

    const result = await dbQuery(
      `UPDATE records
       SET title = COALESCE($2, title),
           payload = COALESCE($3, payload),
           updated_at = now()
       WHERE id = $1
       RETURNING ${SELECT_COLUMNS}`,
      [req.params.id, title, payload]
    );

    if (result.rowCount === 0) {
      res.status(404).json({ error: "Record not found" });
      return;
    }

    res.json(result.rows[0]);
  } catch (error) {
    next(error);
  }
});

app.delete("/api/records/:id", async (req, res, next) => {
  try {
    const result = await dbQuery("DELETE FROM records WHERE id = $1", [req.params.id]);

    if (result.rowCount === 0) {
      res.status(404).json({ error: "Record not found" });
      return;
    }

    res.status(204).send();
  } catch (error) {
    next(error);
  }
});

app.use((_req, res) => {
  res.status(404).json({ error: "Not found" });
});

app.use((error, _req, res, _next) => {
  console.error(error);

  if (error.type === "entity.parse.failed") {
    return res.status(400).json({ error: "Invalid JSON" });
  }

  const status = error.code === "22P02" ? 400 : 500;

  res.status(status).json({
    error: process.env.NODE_ENV === "production" ? "Internal server error" : error.message,
  });
});

const server = app.listen(port, "0.0.0.0", () => {
  console.log(`Backend API listening on port ${port}`);
});

const shutdown = async (signal) => {
  console.log(`Received ${signal}; shutting down gracefully`);

  server.close(async () => {
    try {
      await closeDatabase();
    } finally {
      process.exit(signal === "SIGTERM" ? 0 : 1);
    }
  });

  setTimeout(() => process.exit(1), 10000).unref();
};

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
```

```text title="backend/.dockerignore"
node_modules
dist
coverage
.env
.env.*
!.env.example
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
.git
.gitignore
Dockerfile
```

```dockerfile title="frontend/Dockerfile"
FROM node:20-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm install --no-audit --no-fund


FROM node:20-alpine AS build

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN npm run build


FROM nginx:1.27-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health >/dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

```json title="frontend/package.json"
{
  "name": "storage-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0"
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

```html title="frontend/index.html"
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

```js title="frontend/vite.config.js"
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:3000",
        changeOrigin: true
      }
    }
  }
});
```

```nginx title="frontend/nginx.conf"
server {
  listen 80;
  server_name _;

  root /usr/share/nginx/html;
  index index.html;

  location = /health {
    default_type text/plain;
    return 200 "ok\n";
  }

  location /api/ {
    proxy_pass http://backend:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_read_timeout 60s;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

```js title="frontend/src/main.jsx"
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

```jsx title="frontend/src/App.jsx"
import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

function formatDateTime(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

function parsePayload(value) {
  if (!value.trim()) {
    return {};
  }

  try {
    return JSON.parse(value);
  } catch (error) {
    throw new Error("Payload must be valid JSON.");
  }
}

function emptyForm() {
  return { title: "", payload: "{}" };
}

export default function App() {
  const [records, setRecords] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: "", text: "" });

  async function loadRecords() {
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/records`);

      if (!response.ok) {
        throw new Error(`Failed to load records: ${response.status}`);
      }

      const data = await response.json();
      setRecords(data);
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadRecords();
  }, []);

  function editRecord(record) {
    setEditingId(record.id);
    setForm({
      title: record.title,
      payload: JSON.stringify(record.payload ?? {}, null, 2)
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);

    try {
      const payload = parsePayload(form.payload);
      const method = editingId ? "PATCH" : "POST";
      const url = editingId ? `${API_BASE}/records/${editingId}` : `${API_BASE}/records`;

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: form.title.trim() || "Untitled",
          payload
        })
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(body || `Request failed: ${response.status}`);
      }

      setForm(emptyForm());
      setEditingId(null);
      setMessage({
        type: "success",
        text: editingId ? "Record updated successfully." : "Record created successfully."
      });

      await loadRecords();
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  async function deleteRecord(id) {
    const confirmed = window.confirm("Delete this record?");

    if (!confirmed) {
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/records/${id}`, { method: "DELETE" });

      if (!response.ok) {
        throw new Error(`Failed to delete record: ${response.status}`);
      }

      setMessage({ type: "success", text: "Record deleted successfully." });
      await loadRecords();
    } catch (error) {
      setMessage({ type: "error", text: error.message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">Microservices Data Storage</p>
        <h1>Store and manage JSON records</h1>
        <p className="hero-copy">
          The React frontend talks to the Express API, which persists records in PostgreSQL.
        </p>
      </section>

      {message.text && (
        <div
          className={`message ${message.type}`}
          role={message.type === "error" ? "alert" : "status"}
        >
          {message.text}
        </div>
      )}

      <section className="layout">
        <form className="card form-card" onSubmit={handleSubmit}>
          <div className="card-header">
            <h2>{editingId ? "Edit record" : "Create record"}</h2>
            <span>{records.length} stored</span>
          </div>

          <label htmlFor="title">Title</label>
          <input
            id="title"
            type="text"
            value={form.title}
            maxLength={255}
            placeholder="Example record"
            onChange={(event) => setForm({ ...form, title: event.target.value })}
          />

          <label htmlFor="payload">Payload JSON</label>
          <textarea
            id="payload"
            value={form.payload}
            spellCheck={false}
            onChange={(event) => setForm({ ...form, payload: event.target.value })}
          />

          <div className="button-row">
            <button type="submit" disabled={loading}>
              {loading ? "Working..." : editingId ? "Update record" : "Create record"}
            </button>

            {editingId && (
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setEditingId(null);
                  setForm(emptyForm());
                }}
              >
                Cancel edit
              </button>
            )}
          </div>
        </form>

        <section className="card records-card">
          <div className="card-header records-header">
            <h2>Records</h2>
            <button type="button" className="secondary" onClick={loadRecords} disabled={loading}>
              Refresh
            </button>
          </div>

          {loading && <p className="muted">Loading records...</p>}
          {!loading && records.length === 0 && <p className="empty-state">No records stored yet.</p>}

          <ul className="records-list">
            {records.map((record) => (
              <li className="record-item" key={record.id}>
                <div className="record-top">
                  <div>
                    <h3>{record.title}</h3>
                    <p className="record-meta">
                      {formatDateTime(record.created_at)} · {record.id}
                    </p>
                  </div>

                  <div className="record-actions">
                    <button type="button" onClick={() => editRecord(record)}>
                      Edit
                    </button>
                    <button type="button" className="danger" onClick={() => deleteRecord(record.id)}>
                      Delete
                    </button>
                  </div>
                </div>

                <pre>{JSON.stringify(record.payload, null, 2)}</pre>
              </li>
            ))}
          </ul>
        </section>
      </section>
    </main>
  );
}
```

```css title="frontend/src/styles.css"
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f6f8fb;
  color: #111827;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.18), transparent 32rem),
    #f6f8fb;
}

button,
input,
textarea {
  font: inherit;
}

button {
  border: 0;
  border-radius: 10px;
  padding: 0.75rem 1rem;
  background: #2563eb;
  color: #ffffff;
  font-weight: 700;
  cursor: pointer;
}

button:hover:not(:disabled) {
  background: #1d4ed8;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

button.secondary {
  background: #e5e7eb;
  color: #111827;
}

button.secondary:hover:not(:disabled) {
  background: #d1d5db;
}

button.danger {
  background: #fee2e2;
  color: #b91c1c;
}

button.danger:hover:not(:disabled) {
  background: #fecaca;
}

.app-shell {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0;
}

.hero {
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #2563eb;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2.2rem, 6vw, 4.8rem);
  line-height: 0.95;
  letter-spacing: -0.06em;
}

.hero-copy {
  max-width: 680px;
  margin: 18px 0 0;
  color: #4b5563;
  font-size: 1.05rem;
}

.layout {
  display: grid;
  grid-template-columns: minmax(280px, 380px) 1fr;
  gap: 24px;
  align-items: start;
}

.card {
  padding: 24px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(14px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 18px;
}

.card h2 {
  margin: 0;
}

.card-header span {
  color: #6b7280;
  font-size: 0.9rem;
}

label {
  display: block;
  margin-top: 16px;
  margin-bottom: 8px;
  font-weight: 700;
}

input,
textarea {
  width: 100%;
  border: 1px solid #d1d5db;
  border-radius: 14px;
  padding: 12px 14px;
  background: #ffffff;
  color: #111827;
  outline: none;
}

textarea {
  min-height: 220px;
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
}

input:focus,
textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 20px;
}

.message {
  margin-bottom: 20px;
  padding: 14px 16px;
  border-radius: 14px;
  font-weight: 700;
}

.message.success {
  background: #dcfce7;
  color: #166534;
}

.message.error {
  background: #fee2e2;
  color: #991b1b;
}

.records-header {
  margin-bottom: 0;
}

.records-header button {
  white-space: nowrap;
}

.muted,
.empty-state {
  color: #6b7280;
}

.records-list {
  display: grid;
  gap: 16px;
  padding: 0;
  margin: 20px 0 0;
  list-style: none;
}

.record-item {
  padding: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: #ffffff;
}

.record-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.record-top h3 {
  margin: 0 0 6px;
}

.record-meta {
  margin: 0;
  color: #6b7280;
  font-size: 0.85rem;
  overflow-wrap: anywhere;
}

.record-actions {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.record-actions button {
  padding: 0.55rem 0.75rem;
  border-radius: 9px;
  font-size: 0.9rem;
}

pre {
  margin: 16px 0 0;
  padding: 14px;
  border-radius: 14px;
  background: #0f172a;
  color: #dbeafe;
  overflow: auto;
  font-size: 0.88rem;
}

@media (max-width: 860px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .record-top {
    flex-direction: column;
  }

  .record-actions {
    width: 100%;
  }

  .record-actions button {
    flex: 1;
  }
}
```

```text title="frontend/.dockerignore"
node_modules
dist
coverage
.env
.env.*
!.env.example
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
.git
.gitignore
Dockerfile
```

# Checker Review
Review verdict: **Mostly compliant / pass with minor warnings.**

- **Multi-stage builds:** ✅ Yes.  
  Both custom microservices use Docker multi-stage builds:
  - `backend/Dockerfile`: `deps` → `build` → `production`
  - `frontend/Dockerfile`: `deps` → `build` → `production`

- **Minimal images:** ✅ Mostly.  
  Final images use Alpine-based bases:
  - Backend: `node:20-alpine`
  - Frontend: `nginx:1.27-alpine`
  - Database: `postgres:16-alpine`

  Build/dev dependencies are not copied into the backend final stage, and the frontend final stage only serves the built static app.

- **Single `docker-compose.yml`:** ✅ Yes.  
  There is one root-level `docker-compose.yml` orchestrating all three services: `frontend`, `backend`, and `database`, with a bridge network and PostgreSQL volume.

Warnings:

- The images are Alpine-based, but not truly “absolute smallest.” `node:20-alpine` and `nginx:1.27-alpine` still include shells/package managers. If strict minimalism is required, consider distroless/static alternatives.
- `depends_on.condition: service_healthy` requires modern Docker Compose support. Legacy `docker-compose` v1 may ignore or reject it. Test with the intended `docker-compose up --build` command.
- Healthchecks are duplicated between Dockerfiles and Compose. Not harmful, but redundant.