import subprocess, sys
from pathlib import Path

ALLOW = {".gitignore", "scripts/gate_scope.py"}

DENY_PREFIX = (".venv/", "venv/", "__pycache__/", "artifacts/")
DENY_FILES  = ("execution_fingerprint.txt", ".env", ".streamlit/secrets.toml")
DENY_SUFFIX = (".csv", ".db", ".sqlite")

def sh(cmd):
    return subprocess.check_output(cmd, text=True).strip()

def changed_files():
    try:
        base = sh(["git", "merge-base", "HEAD", "origin/main"])
        out = sh(["git", "diff", "--name-only", f"{base}..HEAD"])
    except Exception:
        out = sh(["git", "diff", "--name-only", "HEAD~1..HEAD"])
    return [x for x in out.splitlines() if x]

def main():
    files = changed_files()
    violations = []

    for f in files:
        if f not in ALLOW:
            violations.append(("OUT_OF_SCOPE", f))
        if any(f.startswith(p) for p in DENY_PREFIX):
            violations.append(("DENY_PREFIX", f))
        if f in DENY_FILES:
            violations.append(("DENY_FILE", f))
        if f.endswith(DENY_SUFFIX):
            violations.append(("DENY_SUFFIX", f))

    if violations:
        print("❌ SCOPE GATE FAILED")
        for reason, f in violations:
            print(f"- {reason}: {f}")
        sys.exit(2)

    print("✅ SCOPE GATE PASS")
    sys.exit(0)

if __name__ == "__main__":
    main()
