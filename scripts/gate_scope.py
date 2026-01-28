import subprocess, sys

DENY_PREFIX = (".venv/", "venv/", "__pycache__/", "artifacts/")
DENY_FILES  = ("execution_fingerprint.txt", ".env", ".streamlit/secrets.toml")
DENY_SUFFIX = (".csv", ".db", ".sqlite")

def sh(cmd):
    return subprocess.check_output(cmd, text=True)

def changed_files():
    out = sh(["git", "status", "--porcelain"])
    files = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:]  # "XY path" or "?? path"
        files.append(path)
    return files

def main():
    files = changed_files()
    violations = []
    for f in files:
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
