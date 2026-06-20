# Maker Output
```yaml docker-compose.yml
version: "2.4"

services:
  database:
    image: postgres:16-alpine
    container_name: storage-database
    restart: unless-stopped
    environment:
      POSTGRES_DB: storage_db
      POSTGRES_USER: storage_app
      POSTGRES_PASSWORD: storage_app_password
      POSTGRES_INITDB_ARGS: "--auth-host=scram-sha-256"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init.sql:/docker-entrypoint-initdb.d/001-init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U storage_app -d storage_db"]
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
    container_name: storage-backend
    restart: unless-stopped
    environment:
      NODE_ENV: production
      PORT: 3000
      DATABASE_URL: "postgres://storage_app:storage_app_password@database:5432/storage_db"
      DB_POOL_SIZE: 10
      DB_STARTUP_ATTEMPTS: 60
      DB_STARTUP_DELAY_MS: 1000
      CORS_ORIGIN: "http://localhost:8080"
    depends_on:
      database:
        condition: service_healthy
    ports:
      - "3000:3000"
    healthcheck:
      test: ["CMD-SHELL", "node -e \"fetch('http://127.0.0.1:3000/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\""]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 10s
    networks:
      - storage-net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: storage-frontend
    restart: unless-stopped
    depends_on:
      backend:
        condition: service_healthy
    ports:
      - "8080:80"
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://127.0.0.1/health | grep -q \"frontend ok\""]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 5s
    networks:
      - storage-net

volumes:
  postgres_data:

networks:
  storage-net:
    driver: bridge
```

```dockerfile backend/Dockerfile
FROM node:22-alpine AS base

WORKDIR /app

COPY package*.json ./
RUN npm install --no-audit --no-fund

FROM base AS builder

COPY tsconfig.json ./
COPY src ./src

RUN npm run build \
  && npm prune --omit=dev --no-audit --no-fund \
  && npm cache clean --force

FROM node:22-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

RUN addgroup -S app && adduser -S app -G app

COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY package*.json ./

RUN chown -R app:app /app

USER app

EXPOSE 3000

CMD ["node", "dist/index.js"]
```

```text backend/.dockerignore
node_modules
dist
coverage
.env
.env.*
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
.DS_Store
*.tsbuildinfo
```

```json backend/package.json
{
  "name": "storage-backend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "build": "tsc -p tsconfig.json",
    "start": "node dist/index.js",
    "dev": "tsx watch src/index.ts"
  },
  "dependencies": {
    "express": "4.18.3",
    "pg": "8.11.5"
  },
  "devDependencies": {
    "@types/express": "4.17.21",
    "@types/node": "22.10.2",
    "@types/pg": "8.11.6",
    "tsx": "4.7.1",
    "typescript": "5.4.5"
  }
}
```

```json backend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "CommonJS",
    "moduleResolution": "Node",
    "rootDir": "src",
    "outDir": "dist",
    "strict": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "types": ["node"]
  },
  "include": ["src"]
}
```

```sql backend/init.sql
CREATE TABLE IF NOT EXISTS stored_items (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL CHECK (char_length(trim(name)) > 0),
  value TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stored_items_created_at
  ON stored_items (created_at DESC);
```

```typescript backend/src/config.ts
const toPositiveInteger = (name: string, fallback: number): number => {
  const raw = process.env[name];
  const value = raw === undefined || raw === "" ? fallback : Number(raw);

  if (!Number.isInteger(value) || value <= 0) {
    throw new Error(`${name} must be a positive integer`);
  }

  return value;
};

export const config = {
  nodeEnv: process.env.NODE_ENV ?? "production",
  port: toPositiveInteger("PORT", 3000),
  databaseUrl: process.env.DATABASE_URL ?? "postgres://storage_app:storage_app_password@database:5432/storage_db",
  corsOrigin: process.env.CORS_ORIGIN ?? "http://localhost:8080",
  dbStartupAttempts: toPositiveInteger("DB_STARTUP_ATTEMPTS", 60),
  dbStartupDelayMs: toPositiveInteger("DB_STARTUP_DELAY_MS", 1000)
};
```

```typescript backend/src/db.ts
import { Pool } from "pg";
import { config } from "./config";

const poolSize = Number(process.env.DB_POOL_SIZE ?? 10);

if (!Number.isInteger(poolSize) || poolSize <= 0) {
  throw new Error("DB_POOL_SIZE must be a positive integer");
}

export const pool = new Pool({
  connectionString: config.databaseUrl,
  max: poolSize,
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000
});

export async function ensureSchema(): Promise<void> {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS stored_items (
      id BIGSERIAL PRIMARY KEY,
      name TEXT NOT NULL CHECK (char_length(trim(name)) > 0),
      value TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `);

  await pool.query(`
    CREATE INDEX IF NOT EXISTS idx_stored_items_created_at
      ON stored_items (created_at DESC)
  `);
}
```

```typescript backend/src/index.ts
import express, { NextFunction, Request, Response } from "express";
import { config } from "./config";
import { ensureSchema, pool } from "./db";

type StoredItem = {
  id: number;
  name: string;
  value: string | null;
  created_at: Date;
  updated_at: Date;
};

type ItemInput = Pick<StoredItem, "name" | "value">;

class HttpError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "HttpError";
  }
}

const httpError = (status: number, message: string): HttpError => new HttpError(status, message);

const asyncHandler = (
  fn: (req: Request, res: Response, next: NextFunction) => Promise<void>
) => {
  return (req: Request, res: Response, next: NextFunction): void => {
    void fn(req, res, next).catch(next);
  };
};

const app = express();

app.disable("x-powered-by");

app.use((req: Request, res: Response, next: NextFunction): void => {
  if (config.corsOrigin) {
    res.setHeader("Access-Control-Allow-Origin", config.corsOrigin);
  }

  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");

  if (req.method === "OPTIONS") {
    res.sendStatus(204);
    return;
  }

  next();
});

app.use(express.json({ limit: "64kb" }));

app.get(
  "/health",
  asyncHandler(async (_req: Request, res: Response) => {
    await pool.query("SELECT 1");
    res.json({ status: "ok", service: "backend", database: "ok" });
  })
);

app.get(
  "/api/items",
  asyncHandler(async (_req: Request, res: Response) => {
    const result = await pool.query<StoredItem>(
      "SELECT id, name, value, created_at, updated_at FROM stored_items ORDER BY created_at DESC, id DESC"
    );

    res.json(result.rows);
  })
);

app.post(
  "/api/items",
  asyncHandler(async (req: Request, res: Response) => {
    const item = parseItemBody(req.body);

    const result = await pool.query<StoredItem>(
      "INSERT INTO stored_items (name, value) VALUES ($1, $2) RETURNING id, name, value, created_at, updated_at",
      [item.name, item.value]
    );

    res.status(201).json(result.rows[0]);
  })
);

app.get(
  "/api/items/:id",
  asyncHandler(async (req: Request, res: Response) => {
    const id = parseId(req.params.id);

    const result = await pool.query<StoredItem>(
      "SELECT id, name, value, created_at, updated_at FROM stored_items WHERE id = $1",
      [id]
    );

    if (result.rowCount === 0) {
      throw httpError(404, "Item not found");
    }

    res.json(result.rows[0]);
  })
);

app.put(
  "/api/items/:id",
  asyncHandler(async (req: Request, res: Response) => {
    const id = parseId(req.params.id);
    const item = parseItemBody(req.body);

    const result = await pool.query<StoredItem>(
      `UPDATE stored_items
         SET name = $1, value = $2, updated_at = NOW()
       WHERE id = $3
       RETURNING id, name, value, created_at, updated_at`,
      [item.name, item.value, id]
    );

    if (result.rowCount === 0) {
      throw httpError(404, "Item not found");
    }

    res.json(result.rows[0]);
  })
);

app.delete(
  "/api/items/:id",
  asyncHandler(async (req: Request, res: Response) => {
    const id = parseId(req.params.id);

    const result = await pool.query<StoredItem>(
      "DELETE FROM stored_items WHERE id = $1 RETURNING id, name, value, created_at, updated_at",
      [id]
    );

    if (result.rowCount === 0) {
      throw httpError(404, "Item not found");
    }

    res.json({ deleted: result.rows[0] });
  })
);

app.use((err: unknown, _req: Request, res: Response, _next: NextFunction): void => {
  if (err instanceof HttpError) {
    res.status(err.status).json({ error: err.message });
    return;
  }

  const status = err instanceof Error && "status" in err
    ? Number((err as { status: unknown }).status)
    : NaN;

  if (Number.isInteger(status) && status >= 400 && status < 500) {
    res.status(status).json({ error: err instanceof Error ? err.message : "Bad request" });
    return;
  }

  console.error(err);
  res.status(500).json({ error: "Internal server error" });
});

let server: ReturnType<typeof app.listen>;

async function waitForDatabase(): Promise<void> {
  for (let attempt = 1; attempt <= config.dbStartupAttempts; attempt += 1) {
    try {
      await ensureSchema();
      return;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);

      if (attempt === config.dbStartupAttempts) {
        throw error;
      }

      console.warn(`Database unavailable (${attempt}/${config.dbStartupAttempts}): ${message}`);
      await delay(config.dbStartupDelayMs);
    }
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseItemBody(body: unknown): ItemInput {
  if (!body || typeof body !== "object") {
    throw httpError(400, "Request body must be a JSON object");
  }

  const record = body as Record<string, unknown>;
  const name = typeof record.name === "string" ? record.name.trim() : "";

  if (name.length === 0) {
    throw httpError(400, "Field 'name' is required and must be a non-empty string");
  }

  if (record.value !== undefined && record.value !== null && typeof record.value !== "string") {
    throw httpError(400, "Field 'value' must be a string when provided");
  }

  return {
    name,
    value: typeof record.value === "string" ? record.value : null
  };
}

function parseId(value: string): number {
  const id = Number(value);

  if (!Number.isInteger(id) || id <= 0) {
    throw httpError(400, "Item id must be a positive integer");
  }

  return id;
}

function shutdown(signal: NodeJS.Signals): void {
  console.log(`Received ${signal}. Shutting down...`);

  server.close(async () => {
    try {
      await pool.end();
      console.log("Backend stopped.");
      process.exit(0);
    } catch (error) {
      console.error(error);
      process.exit(1);
    }
  });

  setTimeout(() => {
    console.error("Forced shutdown after timeout.");
    process.exit(1);
  }, 10_000).unref();
}

async function main(): Promise<void> {
  await waitForDatabase();

  server = app.listen(config.port, "0.0.0.0", () => {
    console.log(`Backend listening on 0.0.0.0:${config.port}`);
  });

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
}

void main().catch((error) => {
  console.error("Failed to start backend", error);
  process.exit(1);
});
```

```dockerfile frontend/Dockerfile
FROM node:22-alpine AS base

WORKDIR /app

COPY package*.json ./
RUN npm install --no-audit --no-fund

FROM base AS builder

COPY . .

RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

```text frontend/.dockerignore
node_modules
dist
coverage
.env
.env.*
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
.DS_Store
*.tsbuildinfo
```

```json frontend/package.json
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
    "react": "18.2.0",
    "react-dom": "18.2.0"
  },
  "devDependencies": {
    "@types/react": "18.2.79",
    "@types/react-dom": "18.2.25",
    "@vitejs/plugin-react": "4.2.1",
    "typescript": "5.4.5",
    "vite": "5.2.10"
  }
}
```

```json frontend/tsconfig.json
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
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
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
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

```typescript frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:3000"
    }
  },
  preview: {
    host: "0.0.0.0",
    port: 4173
  },
  build: {
    sourcemap: false
  }
});
```

```nginx frontend/nginx.conf
server {
  listen 80;
  server_name _;

  root /usr/share/nginx/html;
  index index.html;

  location = /health {
    default_type text/plain;
    return 200 "frontend ok\n";
  }

  location /api/ {
    proxy_pass http://backend:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 5s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
  }

  location / {
    try_files $uri $uri/ /index.html;
  }
}
```

```typescript frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```typescript frontend/src/App.tsx
import { FormEvent, useEffect, useState } from "react";
import "./styles.css";

type StoredItem = {
  id: number;
  name: string;
  value: string | null;
  created_at: string;
  updated_at: string;
};

type DeleteResponse = {
  deleted: StoredItem;
};

function formatDate(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export default function App() {
  const [items, setItems] = useState<StoredItem[]>([]);
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editValue, setEditValue] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const loadItems = async (): Promise<void> => {
    setLoading(true);
    setError("");

    try {
      const data = await requestJson<StoredItem[]>("/api/items");
      setItems(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load records");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadItems();
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    const trimmedName = name.trim();

    if (!trimmedName) {
      return;
    }

    setLoading(true);
    setError("");
    setStatus("");

    try {
      const created = await requestJson<StoredItem>("/api/items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: trimmedName,
          value: value.trim() || null
        })
      });

      setItems((current) => [created, ...current]);
      setName("");
      setValue("");
      setStatus("Record saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save record");
    } finally {
      setLoading(false);
    }
  };

  const startEdit = (item: StoredItem): void => {
    setEditingId(item.id);
    setEditName(item.name);
    setEditValue(item.value ?? "");
    setError("");
    setStatus("");
  };

  const cancelEdit = (): void => {
    setEditingId(null);
    setEditName("");
    setEditValue("");
  };

  const handleUpdate = async (id: number): Promise<void> => {
    const trimmedName = editName.trim();

    if (!trimmedName) {
      setError("Record name cannot be empty.");
      return;
    }

    setLoading(true);
    setError("");
    setStatus("");

    try {
      const updated = await requestJson<StoredItem>(`/api/items/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: trimmedName,
          value: editValue.trim() || null
        })
      });

      setItems((current) => current.map((item) => (item.id === id ? updated : item)));
      setEditingId(null);
      setEditName("");
      setEditValue("");
      setStatus("Record updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update record");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number): Promise<void> => {
    if (!window.confirm("Delete this record?")) {
      return;
    }

    setLoading(true);
    setError("");
    setStatus("");

    try {
      await requestJson<DeleteResponse>(`/api/items/${id}`, {
        method: "DELETE"
      });

      setItems((current) => current.filter((item) => item.id !== id));

      if (editingId === id) {
        cancelEdit();
      }

      setStatus("Record deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete record");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="eyebrow">Full-stack data storage</p>
        <h1>Microservice Record Store</h1>
        <p className="hero-copy">
          Create, read, update, and delete records through the decoupled backend API.
        </p>
      </header>

      <form className="record-form" onSubmit={handleSubmit}>
        <label htmlFor="record-name">Record name</label>
        <input
          id="record-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Customer, metric, note..."
          disabled={loading}
        />

        <label htmlFor="record-value">Value</label>
        <textarea
          id="record-value"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Optional details"
          disabled={loading}
        />

        <button type="submit" disabled={loading || name.trim().length === 0}>
          Save record
        </button>
      </form>

      {status && (
        <p className="message success" aria-live="polite">
          {status}
        </p>
      )}

      {error && (
        <p className="message error" aria-live="polite">
          {error}
        </p>
      )}

      <section className="records-panel" aria-labelledby="records-heading">
        <div className="records-header">
          <div>
            <p className="eyebrow">Persistent records</p>
            <h2 id="records-heading">Stored data</h2>
          </div>

          <div className="records-actions">
            {loading && <span className="spinner" aria-label="Loading" />}
            <button type="button" onClick={() => void loadItems()} disabled={loading}>
              Refresh
            </button>
          </div>
        </div>

        {items.length === 0 && !loading ? (
          <p className="empty-state">
            No records yet. Add one above to store it in PostgreSQL.
          </p>
        ) : (
          <div className="records-list">
            {items.map((item) => (
              <article className="record-card" key={item.id}>
                {editingId === item.id ? (
                  <form
                    className="edit-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void handleUpdate(item.id);
                    }}
                  >
                    <label htmlFor={`edit-name-${item.id}`}>Name</label>
                    <input
                      id={`edit-name-${item.id}`}
                      value={editName}
                      onChange={(event) => setEditName(event.target.value)}
                      disabled={loading}
                    />

                    <label htmlFor={`edit-value-${item.id}`}>Value</label>
                    <textarea
                      id={`edit-value-${item.id}`}
                      value={editValue}
                      onChange={(event) => setEditValue(event.target.value)}
                      disabled={loading}
                    />

                    <div className="edit-form-buttons">
                      <button type="submit" disabled={loading}>
                        Save changes
                      </button>
                      <button type="button" onClick={cancelEdit} disabled={loading}>
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div className="record-content">
                      <p className="record-id">ID {item.id}</p>
                      <h3>{item.name}</h3>
                      <p className="record-value">{item.value ?? "No value supplied"}</p>
                      <div className="record-meta">
                        <span>Created {formatDate(item.created_at)}</span>
                        <span>Updated {formatDate(item.updated_at)}</span>
                      </div>
                    </div>

                    <div className="record-actions">
                      <button
                        type="button"
                        onClick={() => startEdit(item)}
                        disabled={loading || editingId !== null}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="danger"
                        onClick={() => void handleDelete(item.id)}
                        disabled={loading || editingId !== null}
                      >
                        Delete
                      </button>
                    </div>
                  </>
                )}
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

```css frontend/src/styles.css
:root {
  color: #0f172a;
  background: #eef2ff;
  font-family:
    Inter,
    ui-sans-serif,
    system-ui,
    -apple-system,
    BlinkMacSystemFont,
    "Segoe UI",
    sans-serif;
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
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.22), transparent 34rem),
    radial-gradient(circle at bottom right, rgba(20, 184, 166, 0.18), transparent 30rem),
    linear-gradient(135deg, #eff6ff 0%, #f8fafc 48%, #ecfeff 100%);
}

button,
input,
textarea {
  font: inherit;
}

button {
  border: 0;
  border-radius: 0.85rem;
  padding: 0.8rem 1rem;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
  font-weight: 700;
  transition:
    transform 160ms ease,
    background 160ms ease,
    opacity 160ms ease;
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
  background: #1d4ed8;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
}

button.danger {
  background: #fee2e2;
  color: #991b1b;
}

button.danger:hover:not(:disabled) {
  background: #fecaca;
  color: #7f1d1d;
}

.app-shell {
  width: min(1100px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0;
}

.hero {
  margin-bottom: 28px;
  padding: 32px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 1.5rem;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.1);
  backdrop-filter: blur(14px);
}

.hero h1 {
  margin: 0;
  font-size: clamp(2.2rem, 6vw, 4.6rem);
  line-height: 1;
  letter-spacing: -0.06em;
}

.hero-copy {
  max-width: 680px;
  margin: 16px 0 0;
  color: #475569;
  font-size: 1.05rem;
  line-height: 1.7;
}

.eyebrow {
  margin: 0 0 8px;
  color: #2563eb;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.record-form,
.records-panel {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 1.5rem;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 20px 55px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(14px);
}

.record-form {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: 16px;
  align-items: end;
  margin-bottom: 18px;
  padding: 22px;
}

.record-form label,
.edit-form label {
  display: block;
  margin-bottom: 7px;
  color: #334155;
  font-size: 0.86rem;
  font-weight: 800;
}

.record-form input,
.record-form textarea,
.edit-form input,
.edit-form textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 0.85rem;
  padding: 0.85rem 0.95rem;
  background: #ffffff;
  color: #0f172a;
  outline: none;
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

.record-form input:focus,
.record-form textarea:focus,
.edit-form input:focus,
.edit-form textarea:focus {
  border-color: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.14);
}

.record-form textarea,
.edit-form textarea {
  min-height: 96px;
  resize: vertical;
}

.record-form button {
  height: 48px;
  white-space: nowrap;
}

.message {
  margin: 0 0 18px;
  border-radius: 1rem;
  padding: 0.9rem 1rem;
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

.records-panel {
  overflow: hidden;
  padding: 22px;
}

.records-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 18px;
}

.records-header h2 {
  margin: 0;
  font-size: 1.55rem;
  letter-spacing: -0.03em;
}

.records-actions,
.record-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.records-actions button {
  background: #e0f2fe;
  color: #075985;
}

.records-actions button:hover:not(:disabled) {
  background: #bae6fd;
}

.spinner {
  width: 18px;
  height: 18px;
  border: 3px solid #bfdbfe;
  border-top-color: #2563eb;
  border-radius: 999px;
  animation: spin 800ms linear infinite;
}

.empty-state {
  margin: 0;
  padding: 32px;
  border: 1px dashed #cbd5e1;
  border-radius: 1rem;
  color: #64748b;
  text-align: center;
}

.records-list {
  display: grid;
  gap: 14px;
}

.record-card {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
  border: 1px solid #e2e8f0;
  border-radius: 1.2rem;
  padding: 18px;
  background: #ffffff;
}

.record-content {
  min-width: 0;
}

.record-id {
  margin: 0 0 6px;
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.record-card h3 {
  margin: 0 0 8px;
  font-size: 1.18rem;
  letter-spacing: -0.02em;
}

.record-value {
  margin: 0;
  color: #475569;
  line-height: 1.6;
  white-space: pre-wrap;
}

.record-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
  color: #64748b;
  font-size: 0.85rem;
}

.record-actions button {
  padding: 0.65rem 0.85rem;
  background: #e0f2fe;
  color: #075985;
}

.record-actions button:hover:not(:disabled) {
  background: #bae6fd;
}

.record-actions button.danger {
  background: #fee2e2;
  color: #991b1b;
}

.record-actions button.danger:hover:not(:disabled) {
  background: #fecaca;
  color: #7f1d1d;
}

.edit-form {
  display: grid;
  width: 100%;
  gap: 12px;
}

.edit-form-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 860px) {
  .record-form {
    grid-template-columns: 1fr;
  }

  .record-form button {
    width: 100%;
  }

  .records-header,
  .record-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .record-actions {
    width: 100%;
  }

  .record-actions button {
    flex: 1;
  }
}

@media (max-width: 520px) {
  .app-shell {
    width: min(100% - 20px, 1100px);
    padding: 24px 0;
  }

  .hero,
  .record-form,
  .records-panel {
    border-radius: 1.1rem;
    padding: 18px;
  }
}
```

# Checker Review
## Brief Review

### 1. Multi-stage builds used?
**Pass.**  
Both custom microservices use multi-stage Docker builds:

- `backend/Dockerfile`: `base` → `builder` → `runtime`
- `frontend/Dockerfile`: `base` → `builder` → `runtime`

Build-time dependencies are not copied into the final runtime stages.

### 2. Minimal images used?
**Mostly pass, with warnings.**

- Backend final image uses `node:22-alpine`, which is lightweight.
- Frontend final image uses `nginx:1.27-alpine`, also lightweight.
- Database uses `postgres:16-alpine`.

However, these are not the absolute smallest possible images. They are Alpine-based, which satisfies the spec’s examples, but they are not distroless.

### 3. Single `docker-compose.yml`?
**Pass.**  
There is a single root-level `docker-compose.yml` orchestrating all three required services:

- `frontend`
- `backend`
- `database`

It also defines a bridge network and PostgreSQL volume, and should start with:

```bash
docker-compose up --build
```

## Warnings

- The frontend runtime image runs `nginx:alpine`, which is lightweight but not distroless. It also does not configure a non-root user.
- The backend uses `node:22-alpine`, which is acceptable but not the absolute smallest possible Node runtime.
- `npm install` is used instead of `npm ci`; a lockfile-based install would be more reproducible.
- `version: "2.4"` is legacy Compose syntax. It works, but the `version` field is no longer required in modern Compose files.

## Verdict

**Compliant with the main spec requirements, with minor hardening/minimal-image warnings.**