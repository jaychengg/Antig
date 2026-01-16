# The "Boris" Protocol Rules

## 1. Security & Configuration
- **API Keys**: NEVER hardcode API keys. ALL keys (Google, Perplexity, Gemini) must be loaded from `streamlit.secrets`.
- **Files**:
    - `secrets.toml`: Contains actual keys (Gitignored).
    - `secrets.example.toml`: Template for users.

## 2. Data Truth
- **News Source**: Market news is ONLY valid if fetched from Perplexity API (`sonar-pro`).
- **Hallucinations**: Do not invent news. If the API fails, report the error.

## 3. Architecture (V2.0)
- **The "One-Stop" Rule**: Perplexity output is BACKEND ONLY. The user must NEVER see raw Perplexity JSON/Text. All search data must be processed by Gemini before display.
- **Input Agnosticism**: The app must accept and auto-process:
    - Raw Text (Tickers/Notes)
    - URLs (Articles)
    - YouTube Links (Transcripts)
    - PDF Uploads (Text Extraction)
- **Logic**:
    - **Intel Service**: Perplexity (Backend Search).
    - **Analysis Service**: Gemini 2.0 Flash Exp (Frontend Analysis).

## 4. Analysis Framework (Strict Structure)
Output must ALWAYS follow this format:
1.  **Macro Analysis**: Interest rates, supply chain, geopolitical impact.
2.  **Wyckoff Analysis**: Price structure (Accumulation/Distribution), Volume spread analysis, Phase (A-E).

## 5. Verification Cycle (The Judge)
- **Zero Tolerance**: The app fails if it runs but displays empty data/errors.
- **Self-Correction**: If a verification step fails (e.g., connection error), read the log -> FIX -> RE-TEST immediately.
- **UI TESTING BAN**: Never use dynamic CSS classes. Use Text-Based Selection or aria-labels. Fallback to Python-level API verification.
