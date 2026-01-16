import os
import sys
import requests

def run_checks():
    print("Starting Ralph Wiggum Checks...")

    # Check 1: Secrets File Existence
    secrets_path = os.path.join(".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        print(f"FAIL: {secrets_path} does not exist.")
        sys.exit(1)
    print(f"PASS: {secrets_path} found.")

    # Check 2: Import google.generativeai
    try:
        import google.generativeai
        print("PASS: google.generativeai imported successfully.")
    except ImportError as e:
        print(f"FAIL: Could not import google.generativeai. Error: {e}")
        sys.exit(1)

    # Check 3: Smoke Test (Network)
    try:
        response = requests.get("https://www.google.com", timeout=5)
        if response.status_code == 200:
             print("PASS: Network check to www.google.com successful.")
        else:
             print(f"FAIL: Network check returned status code {response.status_code}")
             sys.exit(1)
    except Exception as e:
        print(f"FAIL: Network check failed. Error: {e}")
        sys.exit(1)

    print("Ralph Wiggum says: 'I'm a helper!' (All Checks Passed)")
    sys.exit(0)

if __name__ == "__main__":
    run_checks()
