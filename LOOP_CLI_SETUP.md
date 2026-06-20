# Loop Engineering CLI Setup Instructions

This document provides step-by-step instructions for utilizing the `@cobusgreyling/loop-engineering` tools in the Antigravity IDE to scaffold budgets, audit loop architectures, and analyze costs.

---

## 1. Scaffold Templates and Budgets

To scaffold the starter configuration, templates, and budget settings for your Daily Triage loop, execute the following command:

```powershell
npx @cobusgreyling/loop-init . --pattern daily-triage
```

### Injecting your OpenRouter API Key
* The scaffold command will create a local `.env` configuration file in the root of the workspace.
* Open the `.env` file and look for the `OPENROUTER_API_KEY` placeholder.
* Replace the placeholder with your actual OpenRouter API key:
  ```env
  OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  ```
* Ensure you also copy `.env.template` variables (like `MAKER_MODEL` and `CHECKER_MODEL`) to `.env` if you want to customize the models.

---

## 2. Audit Loop Readiness

To validate your local architecture, verify correct setups, and calculate a Loop Readiness Score with architectural recommendations, execute:

```powershell
npx @cobusgreyling/loop-audit . --suggest
```

* **Purpose**: This tool analyzes the files (like `triage_agent.py`, `STATE.md`, workflows) to verify the Maker/Checker split, state serialization, and Git branch isolation boundaries, returning suggestions for improving loop resilience.

---

## 3. Estimate Token and Running Costs

To calculate and estimate your daily, weekly, and monthly OpenRouter token usage and financial cost projections before running on automated triggers, run:

```powershell
npx @cobusgreyling/loop-cost
```

* **Purpose**: This uses loop configuration metadata, model pricing, and historical or simulated invocation statistics to calculate expected OpenRouter spend. It helps ensure that you stay within budget boundaries and that API costs do not grow unexpectedly.
