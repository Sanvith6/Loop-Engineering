# Maker Output
```docker-compose.yml
version: "2.4"

services:
  database:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: storage
      POSTGRES_USER: storage
      POSTGRES_PASSWORD: storage_password
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./database/init:/docker-entrypoint-initdb.d:ro
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U storage -d storage"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      NODE_ENV: production
      PORT: 3000
      DB_HOST: database
      DB_PORT: 5432
      DB_NAME: storage
      DB_USER: storage
      DB_PASSWORD: storage_password
      DB_POOL_SIZE: 10
      DB_CONNECT_TIMEOUT_MS: 5000
      DB_IDLE_TIMEOUT_MS: 30000
      CORS_ORIGIN: http://localhost:8080,http://127.0.0.1:8080,http://0.0.0.0:8080
    ports:
      - "3000:3000"
    depends_on:
      database:
        condition: service_healthy
    networks:
      - app-network
    healthcheck:
      test:
        - CMD
        - /nodejs/bin/node
        - -e
        - |
          const http = require("http");
          const req = http.get("http://127.0.0.1:3000/health", (res) => {
            res.resume();
            process.exit(res.statusCode === 200 ? 0 : 1);
          });
          req.on("error", () => process.exit(1));
          req.setTimeout(2000, () => {
            req.destroy();
            process.exit(1);
          });
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 15s

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - app-network
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/ >/dev/null || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 5s

volumes:
  pgdata:

networks:
  app-network:
    driver: bridge
```

```backend/package.json
{
  "name": "storage-backend",
  "version": "1.0.0",
  "private": true,
  "description": "API layer for the full-stack data storage microservice.",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js"
  },
  "engines": {
    "node": ">=20"
  },
  "dependencies": {
    "cors": "2.8.5",
    "express": "4.18.3",
    "pg": "8.11.5"
  }
}
```

```backend/.dockerignore
.git
.gitignore
Dockerfile
.dockerignore
node_modules
npm-debug.log
coverage
.env
.DS_Store
```

```backend/Dockerfile
FROM node:20-bookworm-slim AS build

WORKDIR /app

ENV NODE_ENV=production

COPY package*.json ./
RUN npm install --omit=dev --ignore-scripts --no-audit --no-fund

COPY src ./src

FROM gcr.io/distroless/nodejs20-debian12

WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/src ./src
COPY --from=build /app/package.json ./package.json

USER 65532:65532

EXPOSE 3000

CMD ["src/index.js"]
```

```backend/src/db.js
const { Pool } = require("pg");

const pool = new Pool({
  host: process.env.DB_HOST || "localhost",
  port: Number(process.env.DB_PORT || 5432),
  database: process.env.DB_NAME || "storage",
  user: process.env.DB_USER || "storage",
  password: process.env.DB_PASSWORD || "storage_password",
  max: Number(process.env.DB_POOL_SIZE || 10),
  connectionTimeoutMillis: Number(process.env.DB_CONNECT_TIMEOUT_MS || 5000),
  idleTimeoutMillis: Number(process.env.DB_IDLE_TIMEOUT_MS || 30000)
});

pool.on("error", (error) => {
  console.error("Unexpected database pool error", error);
});

async function query(text, params) {
  const start = Date.now();

  try {
    const result = await pool.query(text, params);
    const duration = Date.now() - start;
    const slowQueryMs = Number(process.env.DB_SLOW_QUERY_MS || 500);

    if (duration > slowQueryMs) {
      console.warn(`Slow database query (${duration}ms): ${text}`);
    }

    return result;
  } catch (error) {
    console.error("Database query failed", error.message);
    throw error;
  }
}

module.exports = {
  pool,
  query
};
```

```backend/src/index.js
const express = require("express");
const cors = require("cors");
const { query, pool } = require("./db");

const app = express();
const PORT = Number(process.env.PORT || 3000);
const corsOrigins = (process.env.CORS_ORIGIN || "http://localhost:8080")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

app.disable("x-powered-by");
app.use(cors({ origin: corsOrigins.includes("*") ? "*" : corsOrigins }));
app.use(express.json({ limit: "1mb" }));

function httpError(status, message) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function parsePositiveInteger(value, fieldName) {
  if (!/^\d+$/.test(String(value))) {
    throw httpError(400, `${fieldName} must be a positive integer`);
  }

  const parsed = Number(value);

  if (!Number.isSafeInteger(parsed)) {
    throw httpError(400, `${fieldName} is too large`);
  }

  return parsed;
}

function parseNonNegativeInteger(value, fieldName) {
  if (!/^\d+$/.test(String(value))) {
    throw httpError(400, `${fieldName} must be a non-negative integer`);
  }

  const parsed = Number(value);

  if (!Number.isSafeInteger(parsed)) {
    throw httpError(400, `${fieldName} is too large`);
  }

  return parsed;
}

function parseOptionalText(value, fieldName, maxLength) {
  if (value === undefined || value === null) {
    return "";
  }

  const text = String(value);

  if (text.length > maxLength) {
    throw httpError(400, `${fieldName} must be ${maxLength} characters or fewer`);
  }

  return text;
}

function parseName(value) {
  const name = parseOptionalText(value, "name", 200).trim();

  if (name.length < 1) {
    throw httpError(400, "name is required");
  }

  return name;
}

function parseValue(value) {
  if (value === undefined || value === null || value === "") {
    return 0;
  }

  if (typeof value !== "number" && typeof value !== "string") {
    throw httpError(400, "value must be a finite number");
  }

  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    throw httpError(400, "value must be a finite number");
  }

  if (parsed < -9999999999 || parsed > 9999999999) {
    throw httpError(400, "value is out of range");
  }

  return Math.round(parsed * 100) / 100;
}

app.get("/health", async (req, res, next) => {
  try {
    await query("SELECT 1 AS ok");

    res.json({
      status: "ok",
      service: "backend",
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    next(error);
  }
});

app.get("/api/items", async (req, res, next) => {
  try {
    const limit = req.query.limit ? parsePositiveInteger(req.query.limit, "limit") : 50;
    const offset = req.query.offset === undefined ? 0 : parseNonNegativeInteger(req.query.offset, "offset");

    if (limit > 100) {
      throw httpError(400, "limit must be between 1 and 100");
    }

    const result = await query(
      `SELECT id, name, description, value, created_at, updated_at
       FROM items
       ORDER BY created_at DESC, id DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset]
    );

    res.json({
      items: result.rows,
      pagination: {
        limit,
        offset
      }
    });
  } catch (error) {
    next(error);
  }
});

app.post("/api/items", async (req, res, next) => {
  try {
    const name = parseName(req.body && req.body.name);
    const description = parseOptionalText(req.body && req.body.description, "description", 2000);
    const value = parseValue(req.body && req.body.value);

    const result = await query(
      `INSERT INTO items (name, description, value)
       VALUES ($1, $2, $3)
       RETURNING id, name, description, value, created_at, updated_at`,
      [name, description, value]
    );

    res.status(201).json({
      item: result.rows[0]
    });
  } catch (error) {
    next(error);
  }
});

app.get("/api/items/:id", async (req, res, next) => {
  try {
    const id = parsePositiveInteger(req.params.id, "id");

    const result = await query(
      `SELECT id, name, description, value, created_at, updated_at
       FROM items
       WHERE id = $1`,
      [id]
    );

    if (!result.rows[0]) {
      throw httpError(404, "item not found");
    }

    res.json({
      item: result.rows[0]
    });
  } catch (error) {
    next(error);
  }
});

app.delete("/api/items/:id", async (req, res, next) => {
  try {
    const id = parsePositiveInteger(req.params.id, "id");

    const result = await query("DELETE FROM items WHERE id = $1", [id]);

    if (result.rowCount === 0) {
      throw httpError(404, "item not found");
    }

    res.status(204).end();
  } catch (error) {
    next(error);
  }
});

app.use((error, req, res, next) => {
  if (res.headersSent) {
    return next(error);
  }

  const status = error.status || 500;
  const isProduction = process.env.NODE_ENV === "production";

  console.error(error);

  res.status(status).json({
    error: status >= 500 ? "internal_server_error" : "request_failed",
    message: status >= 500 && isProduction ? "Internal server error" : error.message
  });
});

const server = app.listen(PORT, "0.0.0.0", () => {
  console.log(`Backend service listening on 0.0.0.0:${PORT}`);
});

async function shutdown(signal) {
  console.log(`Received ${signal}; shutting down`);

  server.close(async () => {
    try {
      await pool.end();
    } catch (error) {
      console.error("Error while closing database pool", error);
    }

    process.exit(0);
  });

  setTimeout(() => process.exit(1), 10000).unref();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
```

```frontend/.dockerignore
.git
.gitignore
Dockerfile
.dockerignore
node_modules
npm-debug.log
.DS_Store
```

```frontend/Dockerfile
FROM alpine:3.20 AS assets

WORKDIR /assets

COPY public/ ./

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=assets /assets/ /usr/share/nginx/html/

EXPOSE 80
```

```frontend/nginx.conf
user nginx;
worker_processes auto;

events {
  worker_connections 1024;
}

http {
  include /etc/nginx/mime.types;
  default_type application/octet-stream;

  sendfile on;
  keepalive_timeout 65;

  server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location / {
      try_files $uri $uri/ /index.html;
    }
  }
}
```

```frontend/public/index.html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Data Storage</title>
    <link rel="stylesheet" href="/styles.css">
    <script src="/config.js"></script>
    <script defer src="/app.js"></script>
  </head>
  <body>
    <main>
      <h1>Data Storage</h1>
      <p class="subtitle">Add, view, and delete records through the backend API.</p>

      <form id="item-form">
        <label class="name-field" for="name">
          Name
          <input id="name" name="name" type="text" maxlength="200" required autocomplete="off">
        </label>

        <label for="value">
          Value
          <input id="value" name="value" type="number" step="0.01" value="0">
        </label>

        <button type="submit">Save item</button>

        <label class="description-field" for="description">
          Description
          <textarea id="description" name="description" maxlength="2000" autocomplete="off"></textarea>
        </label>
      </form>

      <div id="status" role="status" aria-live="polite"></div>

      <section class="table-wrap" aria-labelledby="items-heading">
        <h2 id="items-heading" class="sr-only">Stored items</h2>

        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Description</th>
              <th>Value</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="items">
            <tr>
              <td colspan="6" class="empty">Loading items...</td>
            </tr>
          </tbody>
        </table>
      </section>
    </main>
  </body>
</html>
```

```frontend/public/config.js
const params = new URLSearchParams(window.location.search);
const host = window.location.hostname || "localhost";

window.APP_CONFIG = {
  apiBaseUrl: params.get("api") || `${window.location.protocol}//${host}:3000/api`
};
```

```frontend/public/app.js
const API_BASE_URL = (
  (window.APP_CONFIG && window.APP_CONFIG.apiBaseUrl) ||
  `${window.location.protocol}//${window.location.hostname || "localhost"}:3000/api`
).replace(/\/+$/, "");

const form = document.querySelector("#item-form");
const nameInput = document.querySelector("#name");
const descriptionInput = document.querySelector("#description");
const valueInput = document.querySelector("#value");
const itemsBody = document.querySelector("#items");
const statusBox = document.querySelector("#status");
const valueFormatter = new Intl.NumberFormat(undefined, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2
});

function setStatus(message, isError = false) {
  statusBox.textContent = message;
  statusBox.classList.toggle("error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });

  const text = await response.text();
  let data = {};

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
  }

  if (!response.ok) {
    throw new Error(data.message || `Request failed with status ${response.status}`);
  }

  return data;
}

async function loadItems() {
  setStatus("Loading items...");

  const data = await api("/items");

  renderItems(data.items || []);
  setStatus(`${data.items.length} item(s) loaded.`);
}

function renderItems(items) {
  itemsBody.innerHTML = "";

  if (!items.length) {
    itemsBody.innerHTML = '<tr><td colspan="6" class="empty">No items stored yet.</td></tr>';
    return;
  }

  const fragment = document.createDocumentFragment();

  items.forEach((item) => {
    const row = document.createElement("tr");
    const createdAt = new Date(item.created_at);
    const formattedCreatedAt = Number.isNaN(createdAt.getTime()) ? "Unknown" : createdAt.toLocaleString();

    row.innerHTML = `
      <td>${item.id}</td>
      <td>${escapeHtml(item.name)}</td>
      <td>${escapeHtml(item.description)}</td>
      <td class="number">${valueFormatter.format(Number(item.value) || 0)}</td>
      <td>${formattedCreatedAt}</td>
      <td><button class="danger" type="button" data-delete="${item.id}">Delete</button></td>
    `;

    fragment.appendChild(row);
  });

  itemsBody.appendChild(fragment);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = {
    name: nameInput.value,
    description: descriptionInput.value,
    value: valueInput.value === "" ? 0 : Number(valueInput.value)
  };

  try {
    await api("/items", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    form.reset();
    valueInput.value = "0";

    await loadItems();
    setStatus("Item saved.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete]");

  if (!button) {
    return;
  }

  const id = button.getAttribute("data-delete");

  if (!window.confirm(`Delete item ${id}?`)) {
    return;
  }

  try {
    await api(`/items/${id}`, {
      method: "DELETE"
    });

    await loadItems();
    setStatus("Item deleted.");
  } catch (error) {
    setStatus(error.message, true);
  }
});

loadItems().catch((error) => {
  setStatus(error.message, true);
});
```

```frontend/public/styles.css
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f4f7fb;
  color: #172033;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  display: flex;
  justify-content: center;
  padding: 40px 16px;
  background: linear-gradient(135deg, #eef2ff 0%, #f8fafc 55%, #ecfeff 100%);
}

main {
  width: min(1100px, 100%);
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.12);
  padding: 28px;
}

h1 {
  margin: 0 0 8px;
  font-size: clamp(2rem, 5vw, 3rem);
  letter-spacing: -0.04em;
}

.subtitle {
  margin: 0 0 24px;
  color: #64748b;
}

form {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  align-items: end;
  padding: 18px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #f8fafc;
}

label {
  display: grid;
  gap: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #334155;
}

.name-field {
  grid-column: span 2;
}

.description-field {
  grid-column: 1 / -1;
}

input,
textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 10px 12px;
  font: inherit;
  background: #ffffff;
}

textarea {
  min-height: 76px;
  resize: vertical;
}

button {
  border: 0;
  border-radius: 10px;
  padding: 11px 16px;
  font-weight: 800;
  cursor: pointer;
}

button[type="submit"] {
  background: #2563eb;
  color: #ffffff;
}

button[type="submit"]:hover {
  background: #1d4ed8;
}

.danger {
  background: #fee2e2;
  color: #991b1b;
  padding: 8px 12px;
}

.danger:hover {
  background: #fecaca;
}

#status {
  min-height: 24px;
  margin: 16px 0;
  color: #047857;
  font-weight: 700;
}

#status.error {
  color: #b91c1c;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
}

table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
}

th,
td {
  padding: 14px 16px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
}

th {
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

tr:last-child td {
  border-bottom: 0;
}

.number {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.empty {
  text-align: center;
  color: #64748b;
  padding: 32px !important;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 760px) {
  body {
    padding: 16px;
  }

  main {
    padding: 20px;
  }

  form {
    grid-template-columns: 1fr;
  }

  .name-field {
    grid-column: auto;
  }
}
```

```database/init/001-init.sql
CREATE TABLE IF NOT EXISTS items (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    value DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_items_created_at
    ON items (created_at DESC, id DESC);
```

# Checker Review
## Brief Review

### Multi-stage builds: **Pass**
- **Backend** uses a multi-stage Dockerfile: `node:20-bookworm-slim AS build` → `gcr.io/distroless/nodejs20-debian12`.
- **Frontend** uses a multi-stage Dockerfile: `alpine:3.20 AS assets` → `nginx:1.27-alpine`.

### Minimal images: **Mostly Pass**
- Backend final image is **distroless**, which satisfies the minimal-image requirement well.
- Frontend final image is **nginx:1.27-alpine**, which is lightweight and allowed by the spec.
- Database uses **postgres:16-alpine**.
- No obvious compilers or dev-dependencies appear in final production stages.

### Single `docker-compose.yml`: **Pass**
- There is a root-level `docker-compose.yml`.
- It orchestrates all three required services: frontend, backend, and database.
- It includes networking, database volume, healthchecks, ports, and startup dependencies.
- It should boot with `docker-compose up --build`.

## Warnings / Notes

- Frontend uses `nginx:1.27-alpine`, which is lightweight but not the absolute smallest possible option. If strict minimization is required, consider a distroless/static nginx-style image.
- Modern Docker Compose usually uses `docker compose up --build`; `docker-compose up --build` may require the legacy standalone binary.
- The frontend assumes the app is accessed via `localhost`; remote deployments may need configurable API base URLs.
- Backend distroless images do not include a shell, so debugging inside the container will be limited.
- Consider adding a `package-lock.json` for reproducible backend dependency installs.

## Verdict

The generated code satisfies the specified Docker requirements: custom services use multi-stage builds, final images are lightweight/alpine or distroless, and there is a single root-level `docker-compose.yml`. No blocking mismatch found.