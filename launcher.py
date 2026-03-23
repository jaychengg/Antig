import sys
import subprocess
import os

def outer_ralph_check():
    """
    Checks environment BEFORE app launch to prevent 'Death-on-Import'.
    The Outer Ralph Loop.
    """
    print("🛡️  Initiating Antigravity Outer Ralph Loop...")
    
    # 1. Python Version & Dependency Check
    v = sys.version_info
    print(f"   ℹ️  Python Version: {v.major}.{v.minor}.{v.micro}")
    
    # Check for potential yfinance incompatibility on older Python versions
    if v.major == 3 and v.minor < 10:
        print("   ⚠️  Detected Python < 3.10. Checking compatibility...")
        try:
            import yfinance
            print("   ✅ yfinance imported successfully.")
        except TypeError as e:
            if "unsupported operand type(s) for |" in str(e):
                print("\n❌ CRITICAL ERROR: Incompatible 'yfinance' version.")
                print("   👉 ACTION: Run 'pip install \"yfinance<0.2.40\" --upgrade'")
                sys.exit(1)
            else:
                print(f"   ⚠️  yfinance import warning: {e}")
        except Exception as e:
            print(f"   ❌ Import Error: {e}")
            sys.exit(1)

    print("   🟢 Environment Check Passed. Launching War Room...")
    print("---------------------------------------------------\n")

if __name__ == "__main__":
    # Windows Unicode Fix
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    outer_ralph_check()
    
    # Check if we are in a virtual environment
    # If using 'streamlit run launcher.py' this script actually runs. 
    # But usually we run 'python launcher.py' which spawns 'streamlit run app.py'
    
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py"]
    
    # If arguments are passed to launcher, pass them to streamlit
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
        
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n   🛑 War Room Shutdown.")
    except Exception as e:
        print(f"   ❌ Launch Error: {e}")
