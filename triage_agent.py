#!/usr/bin/env python3
import os
import sys
import subprocess
import json
import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MAKER_MODEL = os.getenv("MAKER_MODEL", "google/gemini-2.5-flash")
CHECKER_MODEL = os.getenv("CHECKER_MODEL", "meta-llama/llama-3.1-70b-instruct")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Assert API key is set
if not OPENROUTER_API_KEY:
    print("Warning: OPENROUTER_API_KEY is not set in environment variables.", file=sys.stderr)

def run_cmd(args, cwd=None):
    """Helper to run shell/git commands and return stdout as string."""
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(args)}: {e.stderr}", file=sys.stderr)
        raise e

# --- Git Connectors & Branch Checkout Isolation ---

def get_git_status():
    """Returns the porcelain git status."""
    return run_cmd(["git", "status", "--porcelain"])

def is_repo_clean():
    """Checks if the working directory has no uncommitted changes."""
    status = get_git_status()
    return len(status) == 0

def get_git_history(limit=10):
    """Retrieves recent commit history."""
    return run_cmd(["git", "log", f"-n", str(limit), "--oneline"])

def get_git_diff_summary():
    """Retrieves a summary of changes in the working directory/staged area."""
    diff_stat = run_cmd(["git", "diff", "--stat"])
    staged_diff_stat = run_cmd(["git", "diff", "--cached", "--stat"])
    
    summary = ""
    if diff_stat:
        summary += f"Unstaged Changes:\n{diff_stat}\n"
    if staged_diff_stat:
        summary += f"Staged Changes:\n{staged_diff_stat}\n"
    return summary if summary else "No local diffs."

def list_files():
    """Lists files in the repository (excluding git/dotfiles where possible)."""
    return run_cmd(["git", "ls-files"])

def prepare_analysis_branch():
    """
    Safely stashes uncommitted changes and checks out a temporary branch
    for the triage run to keep reports/state isolated from the main working branch.
    """
    original_branch = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    stashed = False
    
    if not is_repo_clean():
        print("Working directory is not clean. Stashing changes...")
        run_cmd(["git", "stash", "-u"])
        stashed = True
        
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    triage_branch = f"agent/triage-{timestamp}"
    
    print(f"Creating and checking out branch {triage_branch}...")
    run_cmd(["git", "checkout", "-b", triage_branch])
    
    return original_branch, stashed, triage_branch

def restore_original_branch(original_branch, stashed):
    """Restores the branch context back to original state."""
    print(f"Restoring branch back to {original_branch}...")
    run_cmd(["git", "checkout", original_branch])
    if stashed:
        print("Popping stashed changes...")
        run_cmd(["git", "stash", "pop"])

# --- OpenRouter API Connector ---

def query_openrouter(prompt, system_prompt, model):
    """Sends a request to OpenRouter and returns the text response."""
    if not OPENROUTER_API_KEY:
        print("Cannot query OpenRouter: OPENROUTER_API_KEY is not set.", file=sys.stderr)
        return "[Error: OPENROUTER_API_KEY not configured. Mocking response for testing.]"

    import requests
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/google-deepmind/antigravity",
        "X-Title": "Antigravity Agent Triage Loop"
    }
    
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        resp_json = response.json()
        return resp_json["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"OpenRouter API call failed: {e}", file=sys.stderr)
        raise e

# --- State / Memory Management ---

STATE_FILE = "STATE.md"

def read_state():
    """Reads the local state memory file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "# Agent Triage State\n\nNo prior run history found.\n"

def append_to_state(run_meta, report_path):
    """Appends execution metadata and logs to the state file."""
    timestamp = run_meta["timestamp"]
    commit_hash = run_meta["latest_commit"]
    maker = run_meta["maker_model"]
    checker = run_meta["checker_model"]
    
    new_entry = f"""
## Run: {timestamp}
- **Commit Analyzed**: `{commit_hash}`
- **Maker Model**: `{maker}`
- **Checker Model**: `{checker}`
- **Report Generated**: [{os.path.basename(report_path)}]({report_path})
- **Status**: Completed successfully.

"""
    
    state_content = read_state()
    
    # Insert new run after the main title headers
    if "## Run history" in state_content:
        parts = state_content.split("## Run history", 1)
        updated_content = parts[0] + "## Run history\n" + new_entry + parts[1]
    elif "## Run:" in state_content:
        # Insert before first Run header
        parts = state_content.split("## Run:", 1)
        updated_content = parts[0] + "## Run history\n" + new_entry + "## Run:" + parts[1]
    else:
        # Append to end
        updated_content = state_content + "\n## Run history\n" + new_entry
        
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(updated_content)
    print(f"Updated {STATE_FILE} with run metadata.")

# --- Maker / Checker Logic ---

def execute_triage_loop():
    print("Starting Daily Triage Loop...")
    
    # 1. Gather git context (prior to branching, to analyze actual working state)
    latest_commit = run_cmd(["git", "rev-parse", "HEAD"])[:8]
    git_history = get_git_history(10)
    git_diff = get_git_diff_summary()
    git_status = get_git_status()
    all_files = list_files()
    
    # 2. Read State
    state_history = read_state()
    
    # 3. Enter Branch Isolation
    original_branch, stashed, triage_branch = prepare_analysis_branch()
    
    try:
        # Create reports directory on triage branch
        os.makedirs("reports", exist_ok=True)
        
        # Prepare context blocks for LLM
        context = f"""
--- REPOSITORY STATE CONTEXT ---
Current Branch (Before analysis checkout): {original_branch}
Latest Commit Hash: {latest_commit}

Recent Commit Log (Last 10):
{git_history}

Git Status / Diffs:
{git_status if git_status else "No uncommitted status changes."}
{git_diff}

Files in Repo:
{all_files}

--- STATE MEMORY (STATE.md Content) ---
{state_history}
"""

        # Step 4: Maker (Implementer) Drafts Triage Report
        maker_system_prompt = (
            "You are an expert Daily Triage AI agent. Your task is to analyze the provided "
            "repository history, diffs, and state metadata, and draft a Daily Triage Report.\n"
            "Include:\n"
            "1. Summary of recent work / code activities.\n"
            "2. Health check of current repository files/state.\n"
            "3. Action items or tickets to create for today's development.\n"
            "Ensure the report is objective and based strictly on the provided context."
        )
        
        maker_prompt = f"Please analyze this repository context and draft the daily triage report:\n\n{context}"
        
        print(f"Invoking Maker agent (Model: {MAKER_MODEL})...")
        draft_report = query_openrouter(maker_prompt, maker_system_prompt, MAKER_MODEL)
        
        # Step 5: Checker (Verifier) Reviews Draft
        checker_system_prompt = (
            "You are an expert Quality Assurance and Verifier Agent. Your job is to review "
            "the drafted triage report against the ground-truth repository state context.\n"
            "Check for:\n"
            "1. Accuracy: Ensure no hallucinated commits, files, or modifications are reported.\n"
            "2. Completeness: Ensure all crucial recent changes are mentioned.\n"
            "3. Professional tone and Markdown layout.\n"
            "Refine the draft as necessary. Output ONLY the final verified markdown report. "
            "Do not add conversational preamble before or after the markdown."
        )
        
        checker_prompt = f"""
Ground Truth Repository Context:
{context}

Drafted Triage Report to verify:
{draft_report}

Please review, verify, and output the final corrected Daily Triage Report:
"""
        
        print(f"Invoking Checker agent (Model: {CHECKER_MODEL})...")
        final_report = query_openrouter(checker_prompt, checker_system_prompt, CHECKER_MODEL)
        
        # Step 6: Save Report and update state
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_path = f"reports/triage_report_{timestamp}.md"
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(final_report)
        print(f"Saved verified report to {report_path}")
        
        # Update State file
        run_meta = {
            "timestamp": datetime.datetime.now().isoformat(),
            "latest_commit": latest_commit,
            "maker_model": MAKER_MODEL,
            "checker_model": CHECKER_MODEL
        }
        append_to_state(run_meta, report_path)
        
        # Commit local state and report to the triage branch
        print("Committing report and updated state to the triage branch...")
        run_cmd(["git", "add", "reports/", STATE_FILE])
        run_cmd(["git", "commit", "-m", f"agent: daily triage run {timestamp}"])

        if os.getenv("PUSH_TO_REMOTE") == "true":
            print(f"Pushing branch {triage_branch} to origin...")
            run_cmd(["git", "push", "origin", triage_branch])

        print("Triage loop completed successfully in isolation branch.")
        
    except Exception as e:
        print(f"An error occurred during triage loop execution: {e}", file=sys.stderr)
    finally:
        # Restore state
        restore_original_branch(original_branch, stashed)

if __name__ == "__main__":
    # If file is executed directly
    if len(sys.argv) > 1 and sys.argv[1] == "--test-local":
        # Mock OpenRouter query for dry-run testing
        print("Running in LOCAL TEST MODE. Mocking API responses.")
        def query_openrouter(prompt, system_prompt, model):
            return f"# Verified Daily Triage Report (Test Mode)\n\nChecked using {model}.\n- Everything looks normal.\n"
            
    execute_triage_loop()
