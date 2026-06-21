# Maker Output
```yaml
# docker-compose.yml
name: full-stack-data-storage

services:
  database:
    image: postgres:16-alpine
    container_name: data-storage-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: apppassword
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d appdb"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - app-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: data-storage-api
    restart: unless-stopped
    environment:
      NODE_ENV: production
      PORT: 3000
      DATABASE_URL: postgres://appuser:apppassword@database:5432/appdb
    ports:
      - "3000:3000"
    depends_on:
      database:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 15s
    networks:
      - app-network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: data-storage-ui
    restart: unless-stopped
    ports:
      - "8080:80"
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - app-network

volumes:
  postgres_data:

networks:
  app-network:
    driver: bridge
```

```dockerfile
# backend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY src ./src

FROM node:20-alpine AS production

ENV NODE_ENV=production
WORKDIR /app

COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/src ./src

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 3000

CMD ["node", "src/server.js"]
```

```json
{
  "name": "data-storage-backend",
  "version": "1.0.0",
  "private": true,
  "type": "commonjs",
  "scripts": {
    "start": "node src/server.js"
  },
  "dependencies": {
    "express": "^4.18.3",
    "pg": "^8.11.5"
  },
  "devDependencies": {}
}
```

```javascript
// backend/src/server.js
const express = require("express");
const { Pool } = require("pg");

const app = express();
const port = Number(process.env.PORT || 3000);

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: Number(process.env.PG_POOL_MAX || 10),
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000
});

app.use(express.json());

app.get("/health", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.status(200).json({ status: "ok" });
  } catch (error) {
    res.status(503).json({ status: "error", message: error.message });
  }
});

app.get("/api/items", async (_req, res) => {
  try {
    const result = await pool.query(
      "SELECT id, name, description, created_at FROM items ORDER BY created_at DESC"
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ message: "Unable to fetch items", error: error.message });
  }
});

app.post("/api/items", async (req, res) => {
  const { name, description } = req.body;

  if (!name || typeof name !== "string" || name.trim().length === 0) {
    res.status(400).json({ message: "Name is required" });
    return;
  }

  try {
    const result = await pool.query(
      `INSERT INTO items (name, description)
       VALUES ($1, $2)
       RETURNING id, name, description, created_at`,
      [name.trim(), description || ""]
    );

    res.status(201).json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ message: "Unable to create item", error: error.message });
  }
});

app.delete("/api/items/:id", async (req, res) => {
  const { id } = req.params;

  try {
    const result = await pool.query(
      "DELETE FROM items WHERE id = $1 RETURNING id",
      [id]
    );

    if (result.rowCount === 0) {
      res.status(404).json({ message: "Item not found" });
      return;
    }

    res.status(204).send();
  } catch (error) {
    res.status(500).json({ message: "Unable to delete item", error: error.message });
  }
});

pool.on("error", (error) => {
  console.error("Unexpected PostgreSQL client error", error);
  process.exit(1);
});

app.listen(port, "0.0.0.0", () => {
  console.log(`Backend listening on port ${port}`);
});
```

```sql
-- backend/src/init.sql
CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY index.html ./
COPY src ./src

RUN npm run build

FROM nginx:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
```

```json
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
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.2.10",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {}
}
```

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Storage</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

```javascript
// frontend/src/main.jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```javascript
// frontend/src/App.jsx
import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export default function App() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("Loading...");

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [items]);

  async function loadItems() {
    try {
      const response = await fetch(`${API_BASE}/api/items`);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setItems(data);
      setStatus("Ready");
    } catch (error) {
      setStatus(`Unable to load items: ${error.message}`);
    }
  }

  async function createItem(event) {
    event.preventDefault();

    const payload = {
      name: name.trim(),
      description: description.trim()
    };

    if (!payload.name) return;

    try {
      const response = await fetch(`${API_BASE}/api/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) throw new Error(await response.text());

      const created = await response.json();
      setItems((current) => [created, ...current]);
      setName("");
      setDescription("");
      setStatus("Item created");
    } catch (error) {
      setStatus(`Unable to create item: ${error.message}`);
    }
  }

  async function deleteItem(id) {
    try {
      const response = await fetch(`${API_BASE}/api/items/${id}`, {
        method: "DELETE"
      });

      if (!response.ok) throw new Error(await response.text());

      setItems((current) => current.filter((item) => item.id !== id));
      setStatus("Item deleted");
    } catch (error) {
      setStatus(`Unable to delete item: ${error.message}`);
    }
  }

  useEffect(() => {
    loadItems();
  }, []);

  return (
    <main>
      <section className="hero">
        <h1>Full-Stack Data Storage</h1>
        <p>Microservices architecture with frontend, backend, and database services.</p>
        <span>{status}</span>
      </section>

      <section className="grid">
        <form className="card" onSubmit={createItem}>
          <h2>Add Item</h2>
          <label>
            Name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Item name"
              required
            />
          </label>
          <label>
            Description
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Item description"
            />
          </label>
          <button type="submit">Create Item</button>
        </form>

        <section className="card">
          <div className="card-header">
            <h2>Stored Items</h2>
            <button type="button" onClick={loadItems}>Refresh</button>
          </div>

          {sortedItems.length === 0 ? (
            <p className="empty">No items stored yet.</p>
          ) : (
            <ul className="items">
              {sortedItems.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.description || "No description"}</p>
                    <small>{new Date(item.created_at).toLocaleString()}</small>
                  </div>
                  <button type="button" onClick={() => deleteItem(item.id)}>
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>
    </main>
  );
}
```

```css
/* frontend/src/styles.css */
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

button {
  border: 0;
  border-radius: 0.75rem;
  background: #38bdf8;
  color: #082f49;
  cursor: pointer;
  font-weight: 700;
  padding: 0.75rem 1rem;
}

button:hover {
  background: #7dd3fc;
}

main {
  margin: 0 auto;
  max-width: 1120px;
  padding: 2rem;
}

.hero {
  margin-bottom: 2rem;
}

.hero h1 {
  margin: 0 0 0.5rem;
  font-size: clamp(2rem, 5vw, 4rem);
}

.hero p {
  margin: 0 0 1rem;
  color: #94a3b8;
}

.hero span {
  display: inline-flex;
  border: 1px solid #334155;
  border-radius: 999px;
  background: #111827;
  color: #bae6fd;
  padding: 0.35rem 0.75rem;
}

.grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: minmax(280px, 380px) 1fr;
}

.card {
  border: 1px solid #1e293b;
  border-radius: 1rem;
  background: #111827;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  padding: 1.5rem;
}

.card h2 {
  margin-top: 0;
}

.card-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

label {
  color: #cbd5e1;
  display: grid;
  font-weight: 700;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

input,
textarea {
  border: 1px solid #334155;
  border-radius: 0.75rem;
  background: #020617;
  color: #f8fafc;
  font: inherit;
  padding: 0.8rem;
  width: 100%;
}

textarea {
  min-height: 120px;
  resize: vertical;
}

.items {
  display: grid;
  gap: 1rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.items li {
  align-items: center;
  border: 1px solid #1e293b;
  border-radius: 0.75rem;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 1rem;
}

.items p {
  color: #94a3b8;
  margin: 0.25rem 0;
}

.items small {
  color: #64748b;
}

.empty {
  color: #94a3b8;
}

@media (max-width: 800px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .items li {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

```dockerfile
# backend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev

COPY src ./src

FROM node:20-alpine AS production

ENV NODE_ENV=production
WORKDIR /app

COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/src ./src

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 3000

CMD ["node", "src/server.js"]
```

```json
{
  "name": "data-storage-backend",
  "version": "1.0.0",
  "private": true,
  "type": "commonjs",
  "scripts": {
    "start": "node src/server.js"
  },
  "dependencies": {
    "express": "^4.18.3",
    "pg": "^8.11.5"
  },
  "devDependencies": {}
}
```

```javascript
// backend/src/server.js
const express = require("express");
const { Pool } = require("pg");

const app = express();
const port = Number(process.env.PORT || 3000);

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: Number(process.env.PG_POOL_MAX || 10),
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000
});

app.use(express.json());

app.get("/health", async (_req, res) => {
  try {
    await pool.query("SELECT 1");
    res.status(200).json({ status: "ok" });
  } catch (error) {
    res.status(503).json({ status: "error", message: error.message });
  }
});

app.get("/api/items", async (_req, res) => {
  try {
    const result = await pool.query(
      "SELECT id, name, description, created_at FROM items ORDER BY created_at DESC"
    );
    res.json(result.rows);
  } catch (error) {
    res.status(500).json({ message: "Unable to fetch items", error: error.message });
  }
});

app.post("/api/items", async (req, res) => {
  const { name, description } = req.body;

  if (!name || typeof name !== "string" || name.trim().length === 0) {
    res.status(400).json({ message: "Name is required" });
    return;
  }

  try {
    const result = await pool.query(
      `INSERT INTO items (name, description)
       VALUES ($1, $2)
       RETURNING id, name, description, created_at`,
      [name.trim(), description || ""]
    );

    res.status(201).json(result.rows[0]);
  } catch (error) {
    res.status(500).json({ message: "Unable to create item", error: error.message });
  }
});

app.delete("/api/items/:id", async (req, res) => {
  const { id } = req.params;

  try {
    const result = await pool.query(
      "DELETE FROM items WHERE id = $1 RETURNING id",
      [id]
    );

    if (result.rowCount === 0) {
      res.status(404).json({ message: "Item not found" });
      return;
    }

    res.status(204).send();
  } catch (error) {
    res.status(500).json({ message: "Unable to delete item", error: error.message });
  }
});

pool.on("error", (error) => {
  console.error("Unexpected PostgreSQL client error", error);
  process.exit(1);
});

app.listen(port, "0.0.0.0", () => {
  console.log(`Backend listening on port ${port}`);
});
```

```sql
-- backend/src/init.sql
CREATE TABLE IF NOT EXISTS items (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY index.html ./
COPY src ./src

RUN npm run build

FROM nginx:1.27-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
```

```json
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
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.2.10",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {}
}
```

```html
<!-- frontend/index.html -->
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Data Storage</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

```javascript
// frontend/src/main.jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```javascript
// frontend/src/App.jsx
import { useEffect, useMemo, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export default function App() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("Loading...");

  const sortedItems = useMemo(() => {
    return [...items].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [items]);

  async function loadItems() {
    try {
      const response = await fetch(`${API_BASE}/api/items`);
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      setItems(data);
      setStatus("Ready");
    } catch (error) {
      setStatus(`Unable to load items: ${error.message}`);
    }
  }

  async function createItem(event) {
    event.preventDefault();

    const payload = {
      name: name.trim(),
      description: description.trim()
    };

    if (!payload.name) return;

    try {
      const response = await fetch(`${API_BASE}/api/items`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) throw new Error(await response.text());

      const created = await response.json();
      setItems((current) => [created, ...current]);
      setName("");
      setDescription("");
      setStatus("Item created");
    } catch (error) {
      setStatus(`Unable to create item: ${error.message}`);
    }
  }

  async function deleteItem(id) {
    try {
      const response = await fetch(`${API_BASE}/api/items/${id}`, {
        method: "DELETE"
      });

      if (!response.ok) throw new Error(await response.text());

      setItems((current) => current.filter((item) => item.id !== id));
      setStatus("Item deleted");
    } catch (error) {
      setStatus(`Unable to delete item: ${error.message}`);
    }
  }

  useEffect(() => {
    loadItems();
  }, []);

  return (
    <main>
      <section className="hero">
        <h1>Full-Stack Data Storage</h1>
        <p>Microservices architecture with frontend, backend, and database services.</p>
        <span>{status}</span>
      </section>

      <section className="grid">
        <form className="card" onSubmit={createItem}>
          <h2>Add Item</h2>
          <label>
            Name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Item name"
              required
            />
          </label>
          <label>
            Description
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Item description"
            />
          </label>
          <button type="submit">Create Item</button>
        </form>

        <section className="card">
          <div className="card-header">
            <h2>Stored Items</h2>
            <button type="button" onClick={loadItems}>Refresh</button>
          </div>

          {sortedItems.length === 0 ? (
            <p className="empty">No items stored yet.</p>
          ) : (
            <ul className="items">
              {sortedItems.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <p>{item.description || "No description"}</p>
                    <small>{new Date(item.created_at).toLocaleString()}</small>
                  </div>
                  <button type="button" onClick={() => deleteItem(item.id)}>
                    Delete
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </section>
    </main>
  );
}
```

```css
/* frontend/src/styles.css */
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

button {
  border: 0;
  border-radius: 0.75rem;
  background: #38bdf8;
  color: #082f49;
  cursor: pointer;
  font-weight: 700;
  padding: 0.75rem 1rem;
}

button:hover {
  background: #7dd3fc;
}

main {
  margin: 0 auto;
  max-width: 1120px;
  padding: 2rem;
}

.hero {
  margin-bottom: 2rem;
}

.hero h1 {
  margin: 0 0 0.5rem;
  font-size: clamp(2rem, 5vw, 4rem);
}

.hero p {
  margin: 0 0 1rem;
  color: #94a3b8;
}

.hero span {
  display: inline-flex;
  border: 1px solid #334155;
  border-radius: 999px;
  background: #111827;
  color: #bae6fd;
  padding: 0.35rem 0.75rem;
}

.grid {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: minmax(280px, 380px) 1fr;
}

.card {
  border: 1px solid #1e293b;
  border-radius: 1rem;
  background: #111827;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
  padding: 1.5rem;
}

.card h2 {
  margin-top: 0;
}

.card-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

label {
  color: #cbd5e1;
  display: grid;
  font-weight: 700;
  gap: 0.4rem;
  margin-bottom: 1rem;
}

input,
textarea {
  border: 1px solid #334155;
  border-radius: 0.75rem;
  background: #020617;
  color: #f8fafc;
  font: inherit;
  padding: 0.8rem;
  width: 100%;
}

textarea {
  min-height: 120px;
  resize: vertical;
}

.items {
  display: grid;
  gap: 1rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.items li {
  align-items: center;
  border: 1px solid #1e293b;
  border-radius: 0.75rem;
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 1rem;
}

.items p {
  color: #94a3b8;
  margin: 0.25rem 0;
}

.items small {
  color: #64748b;
}

.empty {
  color: #94a3b8;
}

@media (max-width: 800px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .items li {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

```nginx
# frontend/nginx.conf
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location /api/ {
        proxy_pass http://backend:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

# Checker Review
Brief review:

- **Multi-stage builds:** ✅ Yes.
  - `backend/Dockerfile` uses `builder` and `production` stages.
  - `frontend/Dockerfile` uses `builder` and `production` stages.

- **Minimal images:** ⚠️ Mostly yes, but not fully optimal.
  - `postgres:16-alpine`, `node:20-alpine`, and `nginx:1.27-alpine` are lightweight.
  - Final images do not appear to include frontend build dependencies or backend source build tooling.
  - However, `node:20-alpine` is not the smallest possible runtime. A smaller Node runtime such as `node:20-alpine` with unnecessary packages removed, or a distroless/`nodejs`-style runtime, would better satisfy the “absolute smallest” requirement.
  - Backend production stage unnecessarily copies `/usr/local/lib/node_modules`, which may include `npm`/tooling from the builder image. This should be removed unless explicitly needed.

- **Single `docker-compose.yml`:** ✅ Yes.
  - There is one root-level `docker-compose.yml`.
  - It defines all three required services: `frontend`, `backend`, and `database`.
  - It uses a bridge network and a PostgreSQL volume.
  - `docker-compose up --build` should start all services.

Necessary warnings:

1. **Backend `init.sql` is not mounted.**
   - `backend/src/init.sql` defines the `items` table, but the `database` service does not mount it into `/docker-entrypoint-initdb.d/`.
   - As written, the table may not exist, causing API failures.

2. **Backend Dockerfile may be larger than necessary.**
   - Remove this line from the production stage:
     ```dockerfile
     COPY --from=builder /usr/local/lib/node_modules /usr/local/lib/node_modules
     ```
   - The final `node:20-alpine` image already includes Node runtime modules.

3. **No `package-lock.json` files are shown.**
   - Both Dockerfiles use `npm ci`, which requires a lockfile.
   - If `package-lock.json` is missing, builds will fail.

4. **Frontend Vite dependencies are listed under `dependencies`, not `devDependencies`.**
   - This is not fatal, but Vite/plugin packages should usually be dev dependencies to reduce build context/install overhead.
   - The final image is still clean because only the built `dist` folder is copied.

5. **Generated code is duplicated.**
   - The backend and frontend files appear twice in the provided code. This is not harmful if accidental, but the actual project should contain each file only once.

Overall: **Mostly compliant**, but fix the missing database init mount and trim the backend production image further to better satisfy the minimal-image requirement.