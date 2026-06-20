# Loop Engineering Architecture & Agents

This repository demonstrates a fully automated **Loop Engineering** setup using autonomous LLM agents. By bridging GitHub Actions with OpenRouter AI models (`nex-agi/nex-n2-pro:free`), this project executes completely decoupled, continuous, and self-verifying workflows.

## The Paradigm: Loop Engineering
Loop Engineering is an advanced agentic architecture that treats LLMs not as conversational chatbots, but as autonomous workers in a background loop. The core pillars used in this repository are:
1. **Maker / Checker Paradigm**: Agents are split into specialized roles. A "Maker" agent performs the heavy lifting (writing code, drafting reports), and a "Checker" agent acts as a strict QA verifier to prevent hallucinations and enforce architectural constraints.
2. **Safe Git Isolation**: Agents never blindly overwrite your active working directory. They stash changes, create isolated branches (`agent/...`), commit their work, and then safely restore your environment.
3. **Durable Memory (`STATE.md`)**: The loop maintains state across executions, ensuring that it has historical context of prior runs without requiring infinite context windows.
4. **Trigger Automation**: Scripts are orchestrated to run autonomously (via cron schedules or `push` triggers in GitHub Actions).

---

## 🤖 The Autonomous Agents

### 1. Daily Triage Agent (`triage_agent.py`)
Runs hourly via GitHub Actions.
- **Goal**: Analyze the repository's health, uncommitted changes, and commit history.
- **Output**: Generates a professional Markdown health report inside the `reports/` folder.
- **Workflow**: Checks out `agent/triage-...`, invokes the Maker/Checker pipeline, updates `STATE.md`, and pushes the branch.

### 2. Scaffold Agent (`scaffold_agent.py`)
Triggered automatically when code is pushed to `main`.
- **Goal**: Reads `APP_SPEC.md` and dynamically scaffolds entire applications based on the provided specifications.
- **Output**: Generates production-ready code (Dockerfiles, config files, backend, frontend) into an `AGENT_GENERATED_CODE.md` file located in a timestamped `scaffolded_app_...` directory.

---

## 🏗️ Generated Output: The Multi-Stage Microservices App

Based on the 12-line specification inside `APP_SPEC.md`, the `scaffold_agent.py` autonomously generated a massive **1,400+ line** full-stack application.

The output is located in the `scaffolded_app_...` directory and includes:

1. **Dockerized Microservices**:
   - `docker-compose.yml`: A root-level orchestration file that boots the entire architecture with a single command.
2. **Strict Multi-Stage Builds**:
   - Two highly optimized `Dockerfile`s (one for the Backend and one for the Frontend). They correctly utilize multi-stage builds (e.g., `AS builder`, `AS runtime`) to drop dev-dependencies and ensure the final production images are minimal (using lightweight `alpine` bases).
3. **Backend Service (Node.js & Express)**:
   - Written strictly in TypeScript.
   - Implements safe database connection pooling using `pg`.
   - Contains automatic initialization scripts (`init.sql`) for a PostgreSQL database.
4. **Frontend Service (React & Vite)**:
   - Scaffolds a complete React + TypeScript app.
   - Includes production-ready Nginx configuration (`nginx.conf`) for reverse proxy routing.

### Running the Generated App

To spin up the AI-generated architecture, simply navigate to the scaffolded app's directory (or extract the code blocks from `AGENT_GENERATED_CODE.md`) and run:

```bash
docker-compose up --build
```

---

*This repository was built entirely using Loop Engineering pipelines to demonstrate the power of autonomous agent architectures.*