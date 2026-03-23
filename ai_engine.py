import google.generativeai as genai
import requests
import streamlit as st
import json

def fetch_perplexity_news(query):
    """
    Fetches news/summary from Perplexity API.
    """
    api_key = st.secrets["PERPLEXITY_API_KEY"]
    url = "https://api.perplexity.ai/chat/completions"
    
    payload = {
        "model": "llama-3.1-sonar-small-128k-online",
        "messages": [
            {
                "role": "system",
                "content": "You are a financial news assistant. Provide a concise, bulleted summary of the latest news and market sentiment for the given topic or ticker."
            },
            {
                "role": "user",
                "content": f"Latest news and analysis for: {query}"
            }
        ]
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"Error fetching Perplexity news: {str(e)}"

def generate_black_box_analysis(content, context="investment analysis"):
    """
    Uses Gemini to analyze provided content (text/transcript).
    """
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""
    You are an expert investment analyst (The Black Box). 
    Analyze the following content in the context of {context}.
    
    Content:
    {content[:10000]} # Limit to avoid context window issues if very large
    
    Please provide:
    1. Key Takeaways (Bullet points)
    2. Bullish/Bearish Sentiment Score (1-10) with reasoning.
    3. Actionable Insights for an investor.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating Gemini analysis: {str(e)}"
