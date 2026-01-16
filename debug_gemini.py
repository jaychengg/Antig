import requests
import os

# Load Key manually or from environment (simulating app)
GEMINI_API_KEY = "AIzaSyAdNzG_rviClVQ_3f_KlauXHiv99jTG9nk"

def test_gemini():
    print("Testing Gemini API Configurations...")
    
    models = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-pro",
        "gemini-1.0-pro",
        "gemini-2.0-flash-exp"
    ]
    
    versions = ["v1beta", "v1"]
    
    for version in versions:
        print(f"\n--- Testing API Version: {version} ---")
        for model in models:
            url = f"https://generativelanguage.googleapis.com/{version}/models/{model}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": "Hello"}]}]
            }
            headers = {"Content-Type": "application/json"}
            
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=5)
                if response.status_code == 200:
                    print(f"SUCCESS! Model: {model} | Version: {version}")
                    print(f"   Response: {response.json()['candidates'][0]['content']['parts'][0]['text'][:50]}...")
                    return # Found a winner
                else:
                    print(f"FAIL: {model} ({version}) -> Status {response.status_code}")
                    # print(f"   Reason: {response.text[:100]}")
            except Exception as e:
                 print(f"ERROR: {model} ({version}) -> {e}")

if __name__ == "__main__":
    test_gemini()
