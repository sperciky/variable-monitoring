import json
import subprocess
import sys
from pathlib import Path


def run(cmd, cwd, capture_output=False, allow_fail=False):
    print(f"> {cmd}")
    result = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture_output
    )

    if result.returncode != 0 and not allow_fail:
        print("❌ Command failed")
        if result.stderr:
            print(result.stderr)
        sys.exit(result.returncode)

    if capture_output and result.stdout is not None:
        return result.stdout.strip()

    return None


with open("config_git_claude_repo.json", "r") as f:
    config = json.load(f)

repo_path = Path(config["repo_path"])
main_branch = config["main_branch"]
merge_branch = config["merge_branch"]
remote = config.get("remote", "origin")
default_message = config.get(
    "default_merge_message",
    "Automated merge from feature branch"
)

if not repo_path.exists():
    print("❌ Repo path does not exist")
    sys.exit(1)

print("✅ Starting automated merge...")
print(f"Repo: {repo_path}")
print(f"Merging: {merge_branch} → {main_branch}\n")

run("git fetch --all", repo_path)

commit_msg = run(
    f"git log {remote}/{merge_branch} -1 --pretty=%B",
    repo_path,
    capture_output=True,
    allow_fail=True
)

if not commit_msg:
    commit_msg = default_message

run(f"git checkout {main_branch}", repo_path)
run(f"git pull {remote} {main_branch}", repo_path)
run(
    f'git merge {remote}/{merge_branch} --no-ff -m "{commit_msg}"',
    repo_path
)
run(f"git push {remote} {main_branch}", repo_path)

print("\n✅ Merge completed successfully.")
