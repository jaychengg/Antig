import sys
import os
import toml
import requests
import google.generativeai as genai

def load_secrets():
    try:
        data = toml.load(".streamlit/secrets.toml")
        return data
    except Exception as e:
        print(f"❌ Error loading secrets: {e}")
        return {}

def test_perplexity(key):
    print("\n📡 Testing Perplexity API (Sonar Pro)...")
    if not key:
        print("   ❌ Missing PERPLEXITY_KEY")
        return

    url = "https://api.perplexity.ai/chat/completions"
    payload = {
        "model": "sonar-pro", # Updated model
        "messages": [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What is the current price of NVDA? Return only the number."}
        ]
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        print(f"   Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Response: {response.json()['choices'][0]['message']['content'][:50]}...")
        else:
            print(f"   ❌ Error: {response.text}")
    except Exception as e:
        print(f"   ❌ Connection Failed: {e}")

def list_gemini_models(key):
    print("\n💎 Listing Available Gemini Models...")
    if not key: return

    try:
        genai.configure(api_key=key)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
        
        # Try a safe fallback test
        print("\n   Testing 'gemini-pro' fallback...")
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Hello")
        print(f"   ✅ Response: {response.text}")
        
    except Exception as e:
        print(f"   ❌ Gemini Error: {e}")

def main():
    print("🔍 DIAGNOSTIC PHASE 2")
    secrets = load_secrets()
    
    p_key = secrets.get("PERPLEXITY_KEY", "") or secrets.get("PERPLEXITY_API_KEY", "")
    g_key = secrets.get("GEMINI_KEY", "") or secrets.get("GEMINI_API_KEY", "")

    test_perplexity(p_key)
    list_gemini_models(g_key)

if __name__ == "__main__":
    main()
