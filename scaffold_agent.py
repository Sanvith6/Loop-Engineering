import os
import subprocess
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (Make sure your .env has OPENROUTER_API_KEY, MAKER_MODEL, CHECKER_MODEL)
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MAKER_MODEL = os.getenv("MAKER_MODEL", "nex-agi/nex-n2-pro:free")
CHECKER_MODEL = os.getenv("CHECKER_MODEL", "nex-agi/nex-n2-pro:free")

def run_git_command(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Git Error: {result.stderr}")
    return result.stdout.strip()

def call_openrouter(prompt, model, system_role):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_role},
            {"role": "user", "content": prompt}
        ]
    }
    response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def main():
    print("🚀 Starting App Scaffold Loop...")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"agent/app-scaffold-{timestamp}"

    # 1. WORKTREE: Safe parallel execution [1]
    original_branch = run_git_command("git rev-parse --abbrev-ref HEAD")
    status = run_git_command("git status --porcelain")
    stashed = False
    if status:
        print("Working directory is not clean. Stashing changes...")
        run_git_command("git stash -u")
        stashed = True

    print(f"🌿 Creating isolated worktree branch: {branch_name}")
    run_git_command(f"git checkout -b {branch_name}")

    # 2. SKILL: Read persistent project knowledge [1]
    print("📚 Reading APP_SPEC.md...")
    try:
        with open("APP_SPEC.md", "r") as f:
            app_spec = f.read()
    except FileNotFoundError:
        print("Error: APP_SPEC.md not found. Please create it first.")
        return

    # 3. SUB-AGENTS (MAKER): Implement the code [1]
    print(f"🛠️ Calling Maker Model ({MAKER_MODEL})...")
    maker_system_prompt = "You are an expert DevOps and Full-Stack Architect. Return ONLY valid code, Dockerfiles, and docker-compose.yml files wrapped in markdown code blocks with their respective filenames."
    maker_prompt = f"Based on this specification, generate the full project files, Dockerfiles using multi-stage builds, and the docker-compose.yml:\n\n{app_spec}"
    maker_output = call_openrouter(maker_prompt, MAKER_MODEL, maker_system_prompt)

    # 4. SUB-AGENTS (CHECKER): Verify the Maker's work [1]
    print(f"🔍 Calling Checker Model ({CHECKER_MODEL})...")
    checker_system_prompt = "You are a strict code reviewer. Verify if the provided code perfectly matches the architectural requirements."
    checker_prompt = f"Review this generated code against the original spec. Check specifically: Are multi-stage builds used? Are images minimal (alpine/distroless)? Is there a single docker-compose.yml? Output a brief review and any necessary warnings.\n\nSpec:\n{app_spec}\n\nGenerated Code:\n{maker_output}"
    checker_output = call_openrouter(checker_prompt, CHECKER_MODEL, checker_system_prompt)

    # 5. PLUGINS / CONNECTORS: Write the files to the filesystem [1]
    print("💾 Saving generated app files to workspace...")
    output_dir = f"scaffolded_app_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    with open(f"{output_dir}/AGENT_GENERATED_CODE.md", "w") as f:
        f.write("# Maker Output\n" + maker_output + "\n\n# Checker Review\n" + checker_output)
    
    # 6. MEMORY / STATE: Update the durable spine outside the conversation [1]
    print("📝 Updating STATE.md run log...")
    log_entry = f"\n- **{timestamp}**: Scaffolded app on branch `{branch_name}` using Maker: `{MAKER_MODEL}`, Checker: `{CHECKER_MODEL}`."
    with open("STATE.md", "a") as f:
        f.write(log_entry)

    # Commit the changes to the isolated branch
    run_git_command("git add .")
    run_git_command(f'git commit -m "feat: agent scaffolded app infrastructure"')
    
    if os.getenv("PUSH_TO_REMOTE") == "true":
        print(f"Pushing branch {branch_name} to origin...")
        run_git_command(f"git push origin {branch_name}")

    # 7. CLEANUP: Restore original state
    print(f"Restoring original branch {original_branch}...")
    run_git_command(f"git checkout {original_branch}")
    if stashed:
        print("Popping stashed changes...")
        run_git_command("git stash pop")
        
    print(f"✅ Scaffold complete! The generated code is safely saved on branch: {branch_name}")

if __name__ == "__main__":
    main()
