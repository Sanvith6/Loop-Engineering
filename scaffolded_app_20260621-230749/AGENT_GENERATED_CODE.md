# Maker Output
**docker-compose.yml**
```yaml
services:
  database:
    image: postgres:16-alpine
    container_name: storage-database
    restart: unless-stopped
    environment:
      POSTGRES_USER: storage_user
      POSTGRES_PASSWORD: storage_password
      POSTGRES_DB: storage_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - storage-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U storage_user -d storage_db"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: storage-backend
    restart: unless-stopped
    environment:
      NODE_ENV: production
      PORT: "3000"
      DATABASE_URL: postgres://storage_user:storage_password@database:5432/storage_db
      CORS_ORIGIN: http://localhost:8080,http://127.0.0.1:8080
      DB_POOL_MAX: "10"
    depends_on:
      database:
        condition: service_healthy
    ports:
      - "3000:3000"
    networks:
      - storage-net
    healthcheck:
      test:
        - CMD
        - node
        - -e
        - "fetch('http://127.0.0.1:3000/health').then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))"
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

  frontend:
    build:
      context: .
      dockerfile: frontend/Dockerfile
      args:
        VITE_API_BASE_URL: http://localhost:3000/api
    container_name: storage-frontend
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "8080:80"
    networks:
      - storage-net
    healthcheck:
      test: ["CMD-SHELL", "wget -q -O /dev/null http://127.0.0.1/ || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  postgres_data:

networks:
  storage-net:
    driver: bridge
```

**backend/Dockerfile**
```dockerfile
FROM node:22-alpine AS deps

WORKDIR /app

ENV NODE_ENV=production

COPY backend/package*.json ./
RUN npm install --omit=dev --no-audit --no-fund


FROM gcr.io/distroless/nodejs22-debian12 AS production

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY --from=deps /app/node_modules ./node_modules
COPY backend/package*.json ./
COPY backend/src ./src

USER nonroot:nonroot

EXPOSE 3000

CMD ["node", "src/index.js"]
```

**backend/package.json**
```json
{
  "name": "storage-backend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=22"
  },
  "scripts": {
    "start": "node src/index.js"
  },
  "dependencies": {
    "cors": "2.8.5",
    "express": "4.21.2",
    "pg": "8.13.1"
  }
}
```

**backend/src/index.js**
```javascript
import express from "express";
import cors from "cors";
import pg from "pg";

const { Pool } = pg;

const app = express();
const port = Number.parseInt(process.env.PORT || "3000", 10);

const allowedOrigins = (process.env.CORS_ORIGIN || "http://localhost:8080")
  .split(",")
  .map((origin) => origin.trim())
  .filter(Boolean);

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: Number.parseInt(process.env.DB_POOL_MAX || "10", 10),
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
});

let databaseReady = false;
let server;

function normalizeText(value, fallback = "") {
  if (typeof value !== "string") return fallback;
  return value.trim();
}

function validateItemInput(body) {
  const errors = [];
  const title = normalizeText(body?.title);
  const description = typeof body?.description === "string" ? body.description.trim() : "";

  if (!title) {
    errors.push("title is required and must be between 1 and 255 characters.");
  }

  if (title.length > 255) {
    errors.push("title must be 255 characters or fewer.");
  }

  if (description.length > 2000) {
    errors.push("description must be 2000 characters or fewer.");
  }

  return { errors, title, description };
}

function parseId(value) {
  const id = Number.parseInt(value, 10);
  return Number.isInteger(id) && id > 0 ? id : null;
}

function toItem(row) {
  return {
    id: row.id,
    title: row.title,
    description: row.description,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

async function runMigrations() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS items (
      id BIGSERIAL PRIMARY KEY,
      title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 255),
      description TEXT NOT NULL DEFAULT '' CHECK (char_length(description) <= 2000),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
  `);

  await pool.query(`
    CREATE OR REPLACE FUNCTION set_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
      NEW.updated_at = now();
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
  `);

  await pool.query(`
    DROP TRIGGER IF EXISTS set_items_updated_at ON items;

    CREATE TRIGGER set_items_updated_at
    BEFORE UPDATE ON items
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();
  `);

  await pool.query(`
    INSERT INTO items (title, description)
    SELECT 'Welcome item', 'This row proves that the backend can read and write to PostgreSQL.'
    WHERE NOT EXISTS (SELECT 1 FROM items LIMIT 1);
  `);

  databaseReady = true;
}

app.use(cors({
  origin(origin, callback) {
    if (!origin || allowedOrigins.includes(origin)) {
      callback(null, true);
      return;
    }

    callback(new Error(`CORS origin ${origin} is not allowed`));
  },
}));

app.use(express.json({ limit: "1mb" }));

app.get("/health", async (_req, res) => {
  try {
    await pool.query("SELECT 1");

    res.json({
      status: databaseReady ? "ok" : "starting",
      service: "backend",
      database: "ok",
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    res.status(503).json({
      status: "error",
      service: "backend",
      database: "unavailable",
      error: error.message,
    });
  }
});

app.get("/api/items", async (_req, res, next) => {
  try {
    const result = await pool.query(
      "SELECT id, title, description, created_at, updated_at FROM items ORDER BY created_at DESC, id DESC"
    );

    res.json({ items: result.rows.map(toItem) });
  } catch (error) {
    next(error);
  }
});

app.post("/api/items", async (req, res, next) => {
  try {
    const { errors, title, description } = validateItemInput(req.body);

    if (errors.length > 0) {
      res.status(400).json({ errors });
      return;
    }

    const result = await pool.query(
      "INSERT INTO items (title, description) VALUES ($1, $2) RETURNING id, title, description, created_at, updated_at",
      [title, description]
    );

    res.status(201).json({ item: toItem(result.rows[0]) });
  } catch (error) {
    next(error);
  }
});

app.get("/api/items/:id", async (req, res, next) => {
  try {
    const id = parseId(req.params.id);

    if (!id) {
      res.status(400).json({ errors: ["id must be a positive integer."] });
      return;
    }

    const result = await pool.query(
      "SELECT id, title, description, created_at, updated_at FROM items WHERE id = $1",
      [id]
    );

    if (result.rowCount === 0) {
      res.status(404).json({ errors: ["Item not found."] });
      return;
    }

    res.json({ item: toItem(result.rows[0]) });
  } catch (error) {
    next(error);
  }
});

app.patch("/api/items/:id", async (req, res, next) => {
  try {
    const id = parseId(req.params.id);

    if (!id) {
      res.status(400).json({ errors: ["id must be a positive integer."] });
      return;
    }

    const titleInput = req.body?.title;
    const descriptionInput = req.body?.description;

    const title = titleInput === undefined ? undefined : normalizeText(titleInput);
    const description = descriptionInput === undefined
      ? undefined
      : typeof descriptionInput === "string"
        ? descriptionInput.trim()
        : undefined;

    const errors = [];

    if (title !== undefined && (title.length < 1 || title.length > 255)) {
      errors.push("title must be between 1 and 255 characters.");
    }

    if (description !== undefined && description.length > 2000) {
      errors.push("description must be 2000 characters or fewer.");
    }

    if (title === undefined && description === undefined) {
      errors.push("Provide at least one field to update.");
    }

    if (errors.length > 0) {
      res.status(400).json({ errors });
      return;
    }

    const fields = [];
    const values = [];

    if (title !== undefined) {
      values.push(title);
      fields.push(`title = $${values.length}`);
    }

    if (description !== undefined) {
      values.push(description);
      fields.push(`description = $${values.length}`);
    }

    values.push(id);
    fields.push("updated_at = now()");

    const result = await pool.query(
      `UPDATE items SET ${fields.join(", ")} WHERE id = $${values.length} RETURNING id, title, description, created_at, updated_at`,
      values
    );

    if (result.rowCount === 0) {
      res.status(404).json({ errors: ["Item not found."] });
      return;
    }

    res.json({ item: toItem(result.rows[0]) });
  } catch (error) {
    next(error);
  }
});

app.delete("/api/items/:id", async (req, res, next) => {
  try {
    const id = parseId(req.params.id);

    if (!id) {
      res.status(400).json({ errors: ["id must be a positive integer."] });
      return;
    }

    const result = await pool.query("DELETE FROM items WHERE id = $1 RETURNING id", [id]);

    if (result.rowCount === 0) {
      res.status(404).json({ errors: ["Item not found."] });
      return;
    }

    res.status(204).send();
  } catch (error) {
    next(error);
  }
});

app.use((error, _req, res, _next) => {
  if (error?.type === "entity.parse.failed") {
    res.status(400).json({ errors: ["Request body must be valid JSON."] });
    return;
  }

  if (error?.message?.startsWith("CORS origin")) {
    res.status(403).json({ errors: [error.message] });
    return;
  }

  console.error(error);
  res.status(500).json({ errors: ["Internal server error."] });
});

async function start() {
  await runMigrations();

  server = app.listen(port, "0.0.0.0", () => {
    console.log(`Backend API listening on port ${port}`);
  });
}

function shutdown(signal) {
  console.log(`Received ${signal}; shutting down gracefully`);

  server?.close(async () => {
    await pool.end();
    process.exit(0);
  });

  setTimeout(() => process.exit(1), 10_000).unref();
}

start().catch((error) => {
  console.error("Failed to start backend:", error);
  process.exit(1);
});

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
```

**frontend/Dockerfile**
```dockerfile
FROM node:22-alpine AS build

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund

COPY frontend/index.html ./index.html
COPY frontend/src ./src

ARG VITE_API_BASE_URL=http://localhost:3000/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build


FROM nginx:1.27-alpine AS runtime

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**frontend/package.json**
```json
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
  "devDependencies": {
    "vite": "^6.0.0"
  }
}
```

**frontend/index.html**
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Storage</title>
  </head>
  <body>
    <main class="app">
      <header class="hero">
        <h1>Data Storage</h1>
        <p>Create, update, and delete persistent records through a decoupled microservices stack.</p>
      </header>

      <section class="panel">
        <form id="item-form">
          <label>
            Title
            <input id="item-title" name="title" type="text" maxlength="255" required />
          </label>

          <label>
            Description
            <textarea id="item-description" name="description" maxlength="2000"></textarea>
          </label>

          <div class="form-actions">
            <button id="submit-button" type="submit">Save item</button>
            <button id="cancel-edit" type="button" hidden>Cancel edit</button>
          </div>
        </form>
      </section>

      <section class="panel">
        <div id="status" class="status" role="status" aria-live="polite"></div>

        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Title</th>
                <th>Description</th>
                <th>Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody id="items-body"></tbody>
          </table>
        </div>
      </section>
    </main>

    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

**frontend/nginx.conf**
```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**frontend/src/main.js**
```javascript
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:3000/api";

const form = document.querySelector("#item-form");
const titleInput = document.querySelector("#item-title");
const descriptionInput = document.querySelector("#item-description");
const submitButton = document.querySelector("#submit-button");
const cancelEditButton = document.querySelector("#cancel-edit");
const tbody = document.querySelector("#items-body");
const statusEl = document.querySelector("#status");

let items = [];
let editingId = null;

function showStatus(message, type = "info") {
  statusEl.textContent = message;
  statusEl.dataset.type = type;
}

function resetForm() {
  form.reset();
  editingId = null;
  submitButton.textContent = "Save item";
  cancelEditButton.hidden = true;
  titleInput.focus();
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const text = await response.text();
  let data = null;

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.slice(0, 200) };
    }
  }

  if (!response.ok) {
    const message =
      data?.errors?.join(" ") ||
      data?.error ||
      `Request failed with status ${response.status}`;

    throw new Error(message);
  }

  return data;
}

async function loadItems() {
  const data = await apiRequest("/items");
  items = data.items;
  renderItems();
}

function renderItems() {
  tbody.replaceChildren();

  if (items.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.className = "empty";
    cell.colSpan = 4;
    cell.textContent = "No items yet. Add one above.";

    row.append(cell);
    tbody.append(row);
    return;
  }

  for (const item of items) {
    const row = document.createElement("tr");

    const title = document.createElement("td");
    title.textContent = item.title;

    const description = document.createElement("td");
    description.textContent = item.description || "—";

    const updatedAt = document.createElement("td");
    updatedAt.textContent = new Date(item.updatedAt).toLocaleString();

    const actions = document.createElement("td");

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "secondary";
    editButton.dataset.edit = item.id;
    editButton.textContent = "Edit";

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "danger";
    deleteButton.dataset.delete = item.id;
    deleteButton.textContent = "Delete";

    actions.append(editButton, deleteButton);
    row.append(title, description, updatedAt, actions);
    tbody.append(row);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const title = titleInput.value.trim();
  const description = descriptionInput.value.trim();

  if (!title) {
    showStatus("Title is required.", "error");
    titleInput.focus();
    return;
  }

  try {
    if (editingId) {
      await apiRequest(`/items/${editingId}`, {
        method: "PATCH",
        body: JSON.stringify({ title, description }),
      });

      showStatus("Item updated.", "success");
    } else {
      await apiRequest("/items", {
        method: "POST",
        body: JSON.stringify({ title, description }),
      });

      showStatus("Item created.", "success");
    }

    resetForm();
    await loadItems();
  } catch (error) {
    showStatus(error.message, "error");
  }
});

tbody.addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit]");
  const deleteButton = event.target.closest("[data-delete]");

  if (editButton) {
    const id = Number(editButton.dataset.edit);
    const item = items.find((entry) => entry.id === id);

    if (!item) return;

    editingId = item.id;
    titleInput.value = item.title;
    descriptionInput.value = item.description || "";
    submitButton.textContent = "Update item";
    cancelEditButton.hidden = false;

    showStatus("Editing item. Save changes or cancel.", "info");
    titleInput.focus();
    return;
  }

  if (deleteButton) {
    const id = Number(deleteButton.dataset.delete);
    const item = items.find((entry) => entry.id === id);

    if (!item) return;
    if (!window.confirm(`Delete "${item.title}"?`)) return;

    try {
      await apiRequest(`/items/${id}`, { method: "DELETE" });

      showStatus("Item deleted.", "success");

      if (editingId === id) {
        resetForm();
      }

      await loadItems();
    } catch (error) {
      showStatus(error.message, "error");
    }
  }
});

cancelEditButton.addEventListener("click", () => {
  resetForm();
  showStatus("Edit cancelled.", "info");
});

loadItems().catch((error) => {
  showStatus(`Unable to load items: ${error.message}`, "error");
});
```

**frontend/src/styles.css**
```css
:root {
  color-scheme: light;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #f8fafc;
  color: #0f172a;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  background: linear-gradient(135deg, #e0f2fe 0%, #f8fafc 45%, #fef3c7 100%);
}

button,
input,
textarea {
  font: inherit;
}

.app {
  width: min(1100px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0;
}

.hero {
  margin-bottom: 24px;
}

.hero h1 {
  margin: 0 0 8px;
  font-size: clamp(2rem, 5vw, 3.5rem);
  line-height: 1;
}

.hero p {
  margin: 0;
  color: #475569;
}

.panel {
  margin-bottom: 24px;
  padding: 24px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid #e2e8f0;
  border-radius: 20px;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.08);
}

form {
  display: grid;
  gap: 16px;
}

label {
  display: grid;
  gap: 8px;
  font-weight: 700;
  color: #334155;
}

input,
textarea {
  width: 100%;
  padding: 12px 14px;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  color: #0f172a;
  outline: none;
  transition: border-color 160ms ease, box-shadow 160ms ease;
}

input:focus,
textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.16);
}

textarea {
  min-height: 110px;
  resize: vertical;
}

.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

button {
  border: 0;
  border-radius: 999px;
  padding: 11px 18px;
  background: #2563eb;
  color: #ffffff;
  font-weight: 800;
  cursor: pointer;
  transition: background 160ms ease, transform 160ms ease;
}

button:hover {
  background: #1d4ed8;
  transform: translateY(-1px);
}

button.secondary {
  background: #e2e8f0;
  color: #0f172a;
}

button.secondary:hover {
  background: #cbd5e1;
}

button.danger {
  background: #fee2e2;
  color: #991b1b;
}

button.danger:hover {
  background: #fecaca;
}

.status {
  min-height: 24px;
  margin-bottom: 16px;
  font-weight: 700;
  color: #64748b;
}

.status[data-type="success"] {
  color: #15803d;
}

.status[data-type="error"] {
  color: #b91c1c;
}

.status[data-type="info"] {
  color: #2563eb;
}

.table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 720px;
  border-collapse: collapse;
}

th,
td {
  padding: 14px 12px;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

th {
  color: #475569;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

td:nth-child(2) {
  max-width: 420px;
  color: #475569;
}

.empty {
  padding: 32px !important;
  text-align: center;
  color: #64748b;
}

@media (max-width: 640px) {
  .app {
    width: min(100% - 24px, 1100px);
    padding: 24px 0;
  }

  .panel {
    padding: 18px;
    border-radius: 16px;
  }
}
```

# Checker Review
## Brief review

**Multi-stage builds: PASS**
- `backend/Dockerfile` uses `node:22-alpine AS deps` → `gcr.io/distroless/nodejs22-debian12 AS production`.
- `frontend/Dockerfile` uses `node:22-alpine AS build` → `nginx:1.27-alpine AS runtime`.
- Database uses official `postgres:16-alpine`; no custom multi-stage build required.

**Minimal images: PASS**
- Final backend image is distroless and does not include npm/dev dependencies/build tools.
- Final frontend image is Alpine-based Nginx and only contains built static assets + Nginx config.
- Database image is Alpine-based.

**Single `docker-compose.yml`: PASS**
- One root-level `docker-compose.yml` orchestrates frontend, backend, and database.
- Includes bridge network, PostgreSQL volume, health checks, and service dependencies.

## Warnings / fixes needed

1. **Backend distroless startup may be wrong**
   - Distroless Node images commonly use Node as the entrypoint. If so, this line:

   ```dockerfile
   CMD ["node", "src/index.js"]
   ```

   may fail. Prefer making it explicit:

   ```dockerfile
   ENTRYPOINT ["/nodejs/bin/node"]
   CMD ["src/index.js"]
   ```

2. **CORS origin is misconfigured**
   - Compose currently sets:

   ```yaml
   CORS_ORIGIN: http://localhost:3000/api,http://127.0.0.1:8080
   ```

   That is not the frontend origin. It should be:

   ```yaml
   CORS_ORIGIN: http://localhost:8080,http://127.0.0.1:8080
   ```

   Otherwise the default frontend at `http://localhost:8080` may be blocked.

3. **Modern Compose required**
   - `depends_on.condition: service_healthy` requires a modern Docker Compose implementation. Legacy `docker-compose` versions may not support it.

## Verdict

The Docker architecture requirements are mostly satisfied: multi-stage builds, minimal final images, and a single compose file are present. However, I would not mark it as perfectly compliant until the backend distroless CMD/ENTRYPOINT and CORS configuration are fixed.