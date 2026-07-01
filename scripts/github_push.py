#!/usr/bin/env python3
"""
GitHub push script — git CLI primary, GitHub API fallback.

Primary path uses git CLI. In the Cowork sandbox the git index can get a
stale `.git/index.lock` that cannot be removed (Operation not permitted),
which makes every git command fail. When that (or any git error) happens,
this script automatically falls back to the GitHub Data API and pushes the
working-tree changes as one atomic commit — no Terminal needed, ever.

Usage:
    python3 github_push.py "your commit message"
    python3 github_push.py "fix: update file" --files path/to/file.py
"""

from __future__ import annotations
import os
import json
import base64
import subprocess
import sys
import urllib.request

REPO_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_PATH, capture_output=True, text=True, check=check)


# ---------------------------------------------------------------- git CLI path

def _git_push(commit_msg: str, explicit_files: list[str] | None = None):
    # Stale lock from sandbox processes — if we can't clear it, bail to API.
    lock = os.path.join(REPO_PATH, ".git", "index.lock")
    if os.path.exists(lock):
        os.remove(lock)  # raises PermissionError in sandbox → caught → API fallback

    if explicit_files:
        for f in explicit_files:
            run(["git", "add", f])
    else:
        run(["git", "add", "-A"])

    status = run(["git", "-c", "core.quotepath=false", "status", "--porcelain"])
    staged = [l for l in status.stdout.splitlines() if l and not l.startswith("??")]
    if not staged:
        print("Nothing to commit — repo is up to date.")
        return

    for l in staged:
        prefix = "  - " if (l.startswith(" D") or l.startswith("D ")) else "  + "
        print(prefix + l[3:])

    result = run(["git", "commit", "-m", commit_msg], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git commit failed: {result.stderr.strip()}")

    result = run(["git", "push", "origin", "main"], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git push failed: {result.stderr.strip()}")

    sha = run(["git", "log", "-1", "--format=%h"]).stdout.strip()
    print(f"\n✅ Pushed via git CLI — {commit_msg}")
    print(f"   Commit: {sha}")


# ------------------------------------------------------------- GitHub API path

def _gh_creds() -> tuple[str, str]:
    """Parse token + owner/repo from the origin remote URL."""
    url = run(["git", "remote", "get-url", "origin"]).stdout.strip()
    # https://USER:TOKEN@github.com/owner/repo.git
    token = url.split("://", 1)[1].split("@", 1)[0].split(":")[-1]
    path = url.split("github.com/", 1)[1]
    if path.endswith(".git"):
        path = path[:-4]
    return token, path


def _api(token: str, url: str, data=None, method=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Authorization": f"token {token}", "User-Agent": "github_push",
                 "Accept": "application/vnd.github+json"},
        method=method,
    )
    return json.load(urllib.request.urlopen(req))


def _changed_files(explicit_files: list[str] | None):
    """Return [(path, is_deleted), ...] from working tree (no lock needed)."""
    if explicit_files:
        return [(f, not os.path.exists(os.path.join(REPO_PATH, f))) for f in explicit_files]
    # -c core.quotepath=false: 唔好將非 ASCII（中文）檔名 octal-escape 做 "\344\275..."，
    # 否則落面 path 攞到嘅係逐個 backslash-digit 嘅字面文字，open() 揾唔到個真檔案。
    status = run(["git", "-c", "core.quotepath=false", "status", "--porcelain"]).stdout.splitlines()
    out = []
    for l in status:
        if not l:
            continue
        path = l[3:].strip().strip('"')
        deleted = l.startswith(" D") or l.startswith("D ")
        out.append((path, deleted))
    return out


def _api_push(commit_msg: str, explicit_files: list[str] | None = None):
    token, repo = _gh_creds()
    base = f"https://api.github.com/repos/{repo}"
    branch = _api(token, base)["default_branch"]

    files = _changed_files(explicit_files)
    if not files:
        print("Nothing to commit — repo is up to date.")
        return

    ref = _api(token, f"{base}/git/refs/heads/{branch}")
    base_commit = ref["object"]["sha"]
    base_tree = _api(token, f"{base}/git/commits/{base_commit}")["tree"]["sha"]

    tree_entries = []
    for path, deleted in files:
        if deleted:
            tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            print(f"  - {path}")
        else:
            abs_path = os.path.join(REPO_PATH, path)
            with open(abs_path, "rb") as fh:
                content = fh.read()
            blob = _api(token, f"{base}/git/blobs",
                        data={"content": base64.b64encode(content).decode(),
                              "encoding": "base64"})
            mode = "100755" if os.access(abs_path, os.X_OK) else "100644"
            tree_entries.append({"path": path, "mode": mode, "type": "blob", "sha": blob["sha"]})
            print(f"  + {path}")

    new_tree = _api(token, f"{base}/git/trees",
                    data={"base_tree": base_tree, "tree": tree_entries})["sha"]
    new_commit = _api(token, f"{base}/git/commits",
                      data={"message": commit_msg, "tree": new_tree,
                            "parents": [base_commit]})["sha"]
    _api(token, f"{base}/git/refs/heads/{branch}",
         data={"sha": new_commit}, method="PATCH")

    print(f"\n✅ Pushed via GitHub API — {commit_msg}")
    print(f"   Commit: {new_commit[:7]} -> {branch}")


# ------------------------------------------------------------------- dispatch

def push(commit_msg: str, explicit_files: list[str] | None = None):
    try:
        _git_push(commit_msg, explicit_files)
    except Exception as e:
        print(f"⚠️  git CLI unavailable ({e}); falling back to GitHub API…")
        _api_push(commit_msg, explicit_files)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("message", help="Commit message")
    parser.add_argument("--files", nargs="+", help="Specific files to push (skips git add -A)")
    args = parser.parse_args()
    push(args.message, explicit_files=args.files)
