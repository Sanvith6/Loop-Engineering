# Maker Output
```yaml:docker-compose.yml
version: "2.4"

services:
  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE: http://localhost:3000
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
    environment:
      VITE_API_BASE: http://localhost:3000
    healthcheck:
      test:
        - CMD
        - wget
        - -q
        - --spider
        - http://127.0.0.1/
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 5s
    restart: unless-stopped
    networks:
      - storage-net

  backend:
    build:
      context: ./backend
    ports:
      - "3000:3000"
    depends_on:
      db:
        condition: service_healthy
    environment:
      NODE_ENV: production
      PORT: "3000"
      HOST: 0.0.0.0
      DATABASE_URL: postgres://appuser:apppassword@db:5432/appdb
    healthcheck:
      test:
        - CMD
        - /nodejs/bin/node
        - "-e"
        - fetch('http://127.0.0.1:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))
      interval: 10s
      timeout: 3s
      retries: 10
      start_period: 10s
    restart: unless-stopped
    networks:
      - storage-net

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: apppassword
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U appuser -d appdb
      interval: 5s
      timeout: 3s
      retries: 10
      start_period: 10s
    restart: unless-stopped
    networks:
      - storage-net

networks:
  storage-net:
    driver: bridge

volumes:
  postgres_data:
```

```json:backend/package.json
{
  "name": "backend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "main": "src/server.js",
  "scripts": {
    "start": "node src/server.js"
  },
  "dependencies": {
    "express": "^4.19.2",
    "pg": "^8.12.0"
  }
}
```

```javascript:backend/src/server.js
import express from "express";
import { Pool } from "pg";

const port = Number.parseInt(process.env.PORT || "3000", 10);
const host = process.env.HOST || "0.0.0.0";
const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl) {
  console.error("DATABASE_URL environment variable is required.");
  process.exit(1);
}

const app = express();
app.disable("x-powered-by");

app.use((req, res, next) => {
  const allowedOrigin = process.env.CORS_ORIGIN || "*";

  res.setHeader("Access-Control-Allow-Origin", allowedOrigin);
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    res.sendStatus(204);
    return;
  }

  next();
});

app.use(express.json({ limit: "1mb" }));

const poolMax = Number.parseInt(process.env.PGPOOL_MAX || "10", 10);

const pool = new Pool({
  connectionString: databaseUrl,
  max: Number.isFinite(poolMax) && poolMax > 0 ? poolMax : 10,
});

const RETURNING_COLUMNS = "id, title, payload, created_at, updated_at";
const SELECT_RECORD = `SELECT ${RETURNING_COLUMNS} FROM records`;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const asyncHandler = (handler) => (req, res, next) => {
  Promise.resolve(handler(req, res, next)).catch(next);
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

function parseLimit(value) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isNaN(parsed) ? 50 : clamp(parsed, 1, 100);
}

function parseOffset(value) {
  const rawValue = Array.isArray(value) ? value[0] : value;
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isNaN(parsed) ? 0 : clamp(parsed, 0, 100000);
}

function parseRecordId(value) {
  const id = Number(value);
  return Number.isInteger(id) && id > 0 ? id : null;
}

function isJsonObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function waitForDatabase() {
  const attempts = Math.max(
    1,
    Number.parseInt(process.env.DB_CONNECT_ATTEMPTS || "30", 10),
  );
  const delayMs = Math.max(
    100,
    Number.parseInt(process.env.DB_CONNECT_DELAY_MS || "1000", 10),
  );

  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await pool.query("SELECT 1");
      return;
    } catch (error) {
      lastError = error;
      console.warn(`Database connection attempt ${attempt}/${attempts} failed: ${error.message}`);
      await sleep(delayMs);
    }
  }

  throw lastError;
}

async function initializeDatabase() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS records (
      id BIGSERIAL PRIMARY KEY,
      title TEXT NOT NULL CHECK (char_length(title) > 0 AND char_length(title) <= 255),
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await pool.query(`
    CREATE INDEX IF NOT EXISTS idx_records_created_at
    ON records (created_at DESC);
  `);
}

app.get(
  "/health",
  asyncHandler(async (_req, res) => {
    await pool.query("SELECT 1");
    res.json({ status: "ok", database: "ok" });
  }),
);

app.get(
  "/api/records",
  asyncHandler(async (req, res) => {
    const limit = parseLimit(req.query.limit);
    const offset = parseOffset(req.query.offset);

    const [recordsResult, countResult] = await Promise.all([
      pool.query(
        `${SELECT_RECORD} ORDER BY created_at DESC, id DESC LIMIT $1 OFFSET $2`,
        [limit, offset],
      ),
      pool.query("SELECT COUNT(*)::int AS total FROM records"),
    ]);

    res.json({
      data: recordsResult.rows,
      pagination: {
        limit,
        offset,
        total: Number(countResult.rows[0].total),
      },
    });
  }),
);

app.post(
  "/api/records",
  asyncHandler(async (req, res) => {
    const title = String(req.body?.title ?? "").trim();

    if (title.length === 0) {
      return res.status(400).json({ message: "title is required" });
    }

    if (title.length > 255) {
      return res.status(400).json({ message: "title must be 255 characters or fewer" });
    }

    const payload = req.body?.payload ?? {};

    if (!isJsonObject(payload)) {
      return res.status(400).json({ message: "payload must be a JSON object" });
    }

    const result = await pool.query(
      `INSERT INTO records (title, payload)
       VALUES ($1, $2::jsonb)
       RETURNING ${RETURNING_COLUMNS}`,
      [title, JSON.stringify(payload)],
    );

    return res.status(201).json(result.rows[0]);
  }),
);

app.get(
  "/api/records/:id",
  asyncHandler(async (req, res) => {
    const id = parseRecordId(req.params.id);

    if (id === null) {
      return res.status(400).json({ message: "id must be a positive integer" });
    }

    const result = await pool.query(`${SELECT_RECORD} WHERE id = $1`, [id]);

    if (result.rowCount === 0) {
      return res.status(404).json({ message: "record not found" });
    }

    return res.json(result.rows[0]);
  }),
);

app.patch(
  "/api/records/:id",
  asyncHandler(async (req, res) => {
    const id = parseRecordId(req.params.id);

    if (id === null) {
      return res.status(400).json({ message: "id must be a positive integer" });
    }

    const body = req.body ?? {};
    const updates = [];
    const values = [];

    if (Object.prototype.hasOwnProperty.call(body, "title")) {
      const title = String(body.title ?? "").trim();

      if (title.length === 0) {
        return res.status(400).json({ message: "title cannot be empty" });
      }

      if (title.length > 255) {
        return res.status(400).json({ message: "title must be 255 characters or fewer" });
      }

      values.push(title);
      updates.push(`title = $${values.length}`);
    }

    if (Object.prototype.hasOwnProperty.call(body, "payload")) {
      const payload = body.payload;

      if (!isJsonObject(payload)) {
        return res.status(400).json({ message: "payload must be a JSON object" });
      }

      values.push(JSON.stringify(payload));
      updates.push(`payload = $${values.length}::jsonb`);
    }

    if (updates.length === 0) {
      return res.status(400).json({ message: "provide title and/or payload" });
    }

    values.push(id);
    updates.push("updated_at = NOW()");

    const result = await pool.query(
      `UPDATE records
       SET ${updates.join(", ")}
       WHERE id = $${values.length}
       RETURNING ${RETURNING_COLUMNS}`,
      values,
    );

    if (result.rowCount === 0) {
      return res.status(404).json({ message: "record not found" });
    }

    return res.json(result.rows[0]);
  }),
);

app.delete(
  "/api/records/:id",
  asyncHandler(async (req, res) => {
    const id = parseRecordId(req.params.id);

    if (id === null) {
      return res.status(400).json({ message: "id must be a positive integer" });
    }

    const result = await pool.query("DELETE FROM records WHERE id = $1 RETURNING id", [id]);

    if (result.rowCount === 0) {
      return res.status(404).json({ message: "record not found" });
    }

    return res.status(204).end();
  }),
);

app.use((_req, res) => {
  res.status(404).json({ message: "route not found" });
});

app.use((error, _req, res, _next) => {
  console.error(error);

  const status = error.status || (error.type === "entity.parse.failed" ? 400 : 500);
  const message = status === 500 ? "Internal server error" : error.message;

  res.status(status).json({ message });
});

let server;

async function start() {
  await waitForDatabase();
  await initializeDatabase();

  server = app.listen(port, host, () => {
    console.log(`Backend API listening on http://${host}:${port}`);
  });
}

function shutdown(signal) {
  console.log(`Received ${signal}; shutting down.`);

  const forceExit = setTimeout(() => {
    console.error("Shutdown timed out; forcing exit.");
    process.exit(1);
  }, 10000);

  forceExit.unref();

  if (!server) {
    pool.end().finally(() => process.exit(0));
    return;
  }

  server.close(async () => {
    try {
      await pool.end();
      process.exit(0);
    } catch (error) {
      console.error("Error while closing database pool:", error);
      process.exit(1);
    }
  });
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));

start().catch((error) => {
  console.error("Failed to start backend:", error);
  pool.end().finally(() => process.exit(1));
});
```

```dockerfile:backend/Dockerfile
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY src ./src

FROM gcr.io/distroless/nodejs20-debian12 AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0

COPY --from=build --chown=nonroot:nonroot /app /app

USER nonroot

EXPOSE 3000

CMD ["src/server.js"]
```

```:dockerignore:backend/.dockerignore
node_modules
coverage
npm-debug.log
.git
.gitignore
Dockerfile
.dockerignore
```

```json:frontend/package.json
{
  "name": "frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "devDependencies": {
    "vite": "^5.4.11"
  }
}
```

```html:frontend/index.html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Storage Microservices</title>
  </head>
  <body>
    <main id="app">
      <section class="hero">
        <p class="eyebrow">Full-stack data storage</p>
        <h1>Microservice Record Store</h1>
        <p>Create, read, update, and delete JSON records through a decoupled API and PostgreSQL.</p>
      </section>

      <section class="panel">
        <form id="record-form">
          <label for="title">Title</label>
          <input
            id="title"
            name="title"
            type="text"
            maxlength="255"
            required
            placeholder="Customer profile"
          />

          <label for="payload">Payload JSON</label>
          <textarea
            id="payload"
            name="payload"
            rows="8"
            spellcheck="false"
          >{
  "status": "active",
  "priority": 1
}</textarea>

          <div class="form-actions">
            <button id="submit-button" type="submit">Save Record</button>
            <button id="cancel-edit" class="secondary" type="button" hidden>Cancel Edit</button>
          </div>

          <p id="status" class="status" role="status">Loading records…</p>
        </form>
      </section>

      <section class="panel">
        <div class="section-title">
          <h2>Stored Records</h2>
          <button id="refresh-button" class="secondary" type="button">Refresh</button>
        </div>

        <p id="empty-state">No records yet. Create one above.</p>
        <div id="records" class="records" aria-live="polite"></div>
      </section>
    </main>

    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

```javascript:frontend/src/main.js
const API_BASE = (import.meta.env.VITE_API_BASE || "http://localhost:3000").replace(/\/$/, "");

const form = document.querySelector("#record-form");
const titleInput = document.querySelector("#title");
const payloadInput = document.querySelector("#payload");
const submitButton = document.querySelector("#submit-button");
const cancelEditButton = document.querySelector("#cancel-edit");
const refreshButton = document.querySelector("#refresh-button");
const recordsEl = document.querySelector("#records");
const emptyState = document.querySelector("#empty-state");
const statusEl = document.querySelector("#status");

let editingId = null;

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const title = titleInput.value.trim();
  const payloadText = payloadInput.value.trim();

  let payload = {};

  if (payloadText.length > 0) {
    try {
      payload = JSON.parse(payloadText);
    } catch {
      setStatus("Payload must be valid JSON.", true);
      return;
    }
  }

  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
    setStatus("Payload must be a JSON object.", true);
    return;
  }

  try {
    const url = editingId
      ? `${API_BASE}/api/records/${editingId}`
      : `${API_BASE}/api/records`;

    const method = editingId ? "PATCH" : "POST";

    await requestJson(url, {
      method,
      body: JSON.stringify({ title, payload }),
    });

    setStatus(editingId ? "Record updated." : "Record created.");
    form.reset();
    editingId = null;
    submitButton.textContent = "Save Record";
    cancelEditButton.hidden = true;

    await loadRecords();
  } catch (error) {
    setStatus(error.message, true);
  }
});

recordsEl.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");

  if (!button) {
    return;
  }

  const id = Number(button.dataset.id);
  const action = button.dataset.action;

  try {
    if (action === "delete") {
      const confirmed = window.confirm("Delete this record?");

      if (!confirmed) {
        return;
      }

      await requestJson(`${API_BASE}/api/records/${id}`, {
        method: "DELETE",
      });

      setStatus("Record deleted.");
      await loadRecords();
    }

    if (action === "edit") {
      await editRecord(id);
    }
  } catch (error) {
    setStatus(error.message, true);
  }
});

cancelEditButton.addEventListener("click", () => {
  form.reset();
  editingId = null;
  submitButton.textContent = "Save Record";
  cancelEditButton.hidden = true;
  setStatus("Edit cancelled.");
});

refreshButton.addEventListener("click", async () => {
  try {
    await loadRecords();
  } catch (error) {
    setStatus(error.message, true);
  }
});

async function loadRecords() {
  setStatus("Loading records…");

  const data = await requestJson(`${API_BASE}/api/records?limit=100&offset=0`);

  recordsEl.replaceChildren(...data.data.map(createRecordCard));
  emptyState.hidden = data.data.length > 0;

  setStatus(`Loaded ${data.data.length} record${data.data.length === 1 ? "" : "s"}.`);
}

async function editRecord(id) {
  const record = await requestJson(`${API_BASE}/api/records/${id}`);

  editingId = record.id;
  titleInput.value = record.title;
  payloadInput.value = JSON.stringify(record.payload, null, 2);
  submitButton.textContent = "Update Record";
  cancelEditButton.hidden = false;
  titleInput.focus();

  setStatus(`Editing record ${record.id}.`);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(data?.message || `Request failed with status ${response.status}`);
  }

  return data;
}

function createRecordCard(record) {
  const card = document.createElement("article");
  card.className = "record-card";

  card.innerHTML = `
    <div class="record-header">
      <div>
        <h3>${escapeHtml(record.title)}</h3>
        <p class="muted">ID: ${record.id}</p>
      </div>
      <div class="record-actions">
        <button type="button" data-action="edit" data-id="${record.id}">Edit</button>
        <button type="button" class="danger" data-action="delete" data-id="${record.id}">Delete</button>
      </div>
    </div>

    <pre>${escapeHtml(JSON.stringify(record.payload, null, 2))}</pre>

    <p class="muted">
      Created ${new Date(record.created_at).toLocaleString()}
    </p>
    <p class="muted">
      Updated ${new Date(record.updated_at).toLocaleString()}
    </p>
  `;

  return card;
}

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.className = isError ? "status error" : "status";
}

function escapeHtml(value) {
  const escapeMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  };

  return String(value).replace(/[&<>"']/g, (char) => escapeMap[char]);
}

loadRecords().catch((error) => {
  setStatus(error.message, true);
});
```

```css:frontend/src/styles.css
:root {
  color: #e5e7eb;
  background: #0f172a;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
}

button,
input,
textarea {
  font: inherit;
}

#app {
  width: min(1100px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0;
}

.hero {
  margin-bottom: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  color: #38bdf8;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h1,
h2,
h3,
p {
  margin-top: 0;
}

h1 {
  margin-bottom: 12px;
  font-size: clamp(2rem, 6vw, 4rem);
  line-height: 1;
}

h2 {
  margin-bottom: 0;
}

h3 {
  margin-bottom: 4px;
}

.hero p:last-child,
.panel > p {
  color: #94a3b8;
}

.panel {
  margin-top: 20px;
  padding: 24px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 20px;
  background: rgba(15, 23, 42, 0.86);
  box-shadow: 0 24px 80px rgba(2, 6, 23, 0.45);
}

form {
  display: grid;
  gap: 16px;
}

label {
  color: #cbd5e1;
  font-weight: 700;
}

input,
textarea {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 12px;
  padding: 12px 14px;
  color: #e5e7eb;
  background: #020617;
  outline: none;
}

input:focus,
textarea:focus {
  border-color: #38bdf8;
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.18);
}

textarea {
  resize: vertical;
  font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}

button {
  border: 0;
  border-radius: 999px;
  padding: 10px 16px;
  color: #082f49;
  background: #38bdf8;
  cursor: pointer;
  font-weight: 800;
}

button:hover {
  background: #7dd3fc;
}

button.secondary {
  color: #e2e8f0;
  background: rgba(148, 163, 184, 0.16);
}

button.secondary:hover {
  background: rgba(148, 163, 184, 0.28);
}

button.danger {
  color: #450a0a;
  background: #fb7185;
}

button.danger:hover {
  background: #fda4af;
}

.form-actions,
.section-title,
.record-header,
.record-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-actions,
.section-title,
.record-header {
  justify-content: space-between;
}

.status {
  min-height: 1.5rem;
  margin: 0;
  color: #86efac;
}

.status.error {
  color: #fca5a5;
}

.records {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

.record-card {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  background: #111827;
}

.record-actions {
  justify-content: flex-end;
}

pre {
  overflow: auto;
  margin: 14px 0;
  padding: 14px;
  border-radius: 12px;
  color: #bfdbfe;
  background: #020617;
  white-space: pre-wrap;
  word-break: break-word;
}

.muted {
  color: #94a3b8;
}

@media (max-width: 720px) {
  #app {
    width: min(100% - 20px, 1100px);
    padding: 28px 0;
  }

  .panel {
    padding: 18px;
  }

  .form-actions,
  .section-title,
  .record-header {
    align-items: stretch;
    flex-direction: column;
  }

  .record-actions {
    justify-content: flex-start;
  }
}
```

```dockerfile:frontend/Dockerfile
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .

ARG VITE_API_BASE=http://localhost:3000
ENV VITE_API_BASE=${VITE_API_BASE}

RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

```nginx:frontend/nginx.conf
server {
  listen 80;
  server_name _;

  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri $uri/ /index.html;
  }

  location ~* \.(?:css|js|mjs|json|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
    expires 1h;
    add_header Cache-Control "public";
  }
}
```

```:dockerignore:frontend/.dockerignore
node_modules
dist
.env
.env.*
npm-debug.log
.git
.gitignore
Dockerfile
.dockerignore
```

# Checker Review
## Brief Review

**Verdict: Mostly compliant with the Docker/architecture requirements, with minor warnings.**

| Requirement | Status | Notes |
|---|---:|---|
| Multi-stage builds for custom services | ✅ Pass | `frontend/Dockerfile` uses `node:20-alpine AS build` → `nginx:1.27-alpine`. `backend/Dockerfile` uses `node:20-alpine AS build` → `gcr.io/distroless/nodejs20-debian12`. |
| Minimal images: Alpine/Distroless, no build deps in final image | ✅ Pass with caveat | Final images are lightweight: backend is distroless, frontend is Alpine/Nginx, database is `postgres:16-alpine`. Build tools/dev dependencies do not appear in final stages. |
| Single root `docker-compose.yml` orchestrating all services | ✅ Pass | One `docker-compose.yml` defines `frontend`, `backend`, and `db`, with bridge networking and a PostgreSQL volume. |

## Warnings

1. **“Absolute smallest” caveat:**  
   `nginx:1.27-alpine` is lightweight and acceptable under the spec, but it is not the absolute smallest possible frontend runtime. If strict minimalism is required, consider a distroless/static static-file server.

2. **Compose compatibility warning:**  
   The file uses `version: "2.4"` and `depends_on.condition: service_healthy`. This works with Compose v2.4-style syntax, but modern Docker Compose often warns that `version` is obsolete. If using the modern CLI, the command is usually:

   ```bash
   docker compose up --build
   ```

3. **Frontend API base is local-only:**  
   `VITE_API_BASE` is baked as `http://localhost:3000`. This works when the browser accesses the app locally at `localhost:8080`, but would need override for remote/hosted deployments.

4. **No package lockfiles:**  
   Both frontend and backend use `npm install` without committed `package-lock.json` files. For reproducible production builds, prefer `npm ci` with lockfiles.

## Overall

The generated Docker setup satisfies the main spec requirements: custom services use multi-stage builds, final images are minimal Alpine/Distroless-based, and a single root `docker-compose.yml` starts all three services.