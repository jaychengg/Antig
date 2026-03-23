import sys
import os
import toml
import warnings

# Suppress annoying warnings for cleaner output
warnings.filterwarnings("ignore")

def print_status(step, msg, status):
    icon = "✅" if status else "❌"
    print(f"[{step}] {icon} {msg}")

def gate_1_secrets():
    """Hard Gate 1: Check Secrets Existence & Key Presence"""
    print("\n🚪 Gate 1: Secrets & Configuration")
    try:
        if not os.path.exists(".streamlit/secrets.toml"):
            print_status("1", "Missing .streamlit/secrets.toml", False)
            return None
            
        data = toml.load(".streamlit/secrets.toml")
        key = data.get("GEMINI_KEY") or data.get("GEMINI_API_KEY")
        
        if not key:
            print_status("1", "No GEMINI_KEY found in secrets", False)
            return None
            
        print_status("1", "Secrets Found & Key Present", True)
        return key
    except Exception as e:
        print_status("1", f"Secrets Read Error: {e}", False)
        return None

def gate_2_sdk():
    """Hard Gate 2: SDK Verification"""
    print("\n🚪 Gate 2: SDK Integrity")
    try:
        import google.generativeai as genai
        version = getattr(genai, '__version__', 'unknown')
        print_status("2", f"google.generativeai (v{version}) imported", True)
        return genai
    except ImportError:
        print_status("2", "MISSING SDK: google.generativeai", False)
        print("   -> Run: pip install google-generativeai")
        return None
    except Exception as e:
        print_status("2", f"SDK Import Error: {e}", False)
        return None

def gate_3_models(genai, key):
    """Hard Gate 3: ListModels (Auth & Capability Check)"""
    print("\n🚪 Gate 3: Model Discovery")
    try:
        genai.configure(api_key=key)
        models = list(genai.list_models())
        
        valid_models = []
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
                
        if not valid_models:
            print_status("3", "Auth OK, but NO generation models found!", False)
            return None
            
        print_status("3", f"Found {len(valid_models)} Capable Models", True)
        # Suggest best
        print(f"   ℹ️  Examples: {valid_models[:3]}")
        return valid_models
    except Exception as e:
        print_status("3", f"ListModels Failed (Auth/Net): {e}", False)
        return None

def gate_4_smoke(genai, model_name):
    """Hard Gate 4: Smoke Test (Generation)"""
    print("\n🚪 Gate 4: Smoke Test (Live Inference)")
    try:
        model = genai.GenerativeModel(model_name)
        res = model.generate_content("Ping", generation_config={"max_output_tokens": 5})
        if res and res.text:
             print_status("4", f"Generation Success: '{res.text.strip()}'", True)
             return True
        else:
             print_status("4", "Empty Response", False)
             return False
    except Exception as e:
         print_status("4", f"Smoke Test Failed: {e}", False)
         return False

def main():
    print("🛡️  RALPH WIGGUM: 4 HARD GATES PROTOCOL")
    print("=======================================")
    
    # Gate 1
    key = gate_1_secrets()
    if not key: sys.exit(1)
    
    # Gate 2
    genai = gate_2_sdk()
    if not genai: sys.exit(1)
    
    # Gate 3
    valid_models = gate_3_models(genai, key)
    if not valid_models: sys.exit(1)
    
    # Selection Logic for Gate 4
    # Try to pick a standard flash model if available, else first one
    target_model = next((m for m in valid_models if 'flash' in m), valid_models[0])
    
    # Gate 4
    if not gate_4_smoke(genai, target_model): sys.exit(1)
    
    print("=======================================")
    print("🟢 RALPH CHECK PASSED. SYSTEM INTEGRITY VERIFIED.")
    sys.exit(0)

if __name__ == "__main__":
    main()
