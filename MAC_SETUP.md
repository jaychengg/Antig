# macOS Setup Guide for Investment War Room

This guide will help you set up and run the **Investment War Room (Antigravity)** project on your MacBook.

## 1. Transferring Code to macOS
Since you cannot access your office OneDrive on your Mac, choose one of these methods:

### Method A: Git (Recommended)
This is the best way to handle code. You likely already have "Git for Windows" installed if you see Source Control.

#### Option 1: Using VS Code (Easier)
1.  **On Windows**:
    *   Click the **Source Control** icon (looks like a branch) in the left sidebar.
    *   Click **Publish to GitHub** (or "Initialize Repository" then "Publish").
    *   Choose **"Publish to GitHub private repository"**.
2.  **On Mac**:
    *   Open VS Code.
    *   Press `Cmd + Shift + P` -> Type "Git: Clone".
    *   Select "Clone from GitHub" and choose your new repo.

#### Option 2: Command Line
1.  **On Windows**:
    *   Initialize Git (if not done): `git init`
    *   Create a repository on GitHub (personal account).
    *   Push your code:
        ```bash
        git add .
        git commit -m "Initial commit"
        git remote add origin <your-github-repo-url>
        git push -u origin main
        ```
2.  **On Mac**:
    *   Clone it: `git clone <your-github-repo-url>`

### Method B: The "Quick & Dirty" (ZIP)
1.  **On Windows**:
    *   Select all files in `Documents/Antig`.
    *   Right-click -> **Send to -> Compressed (zipped) folder**.
    *   Email this ZIP to yourself, or upload it to a personal Google Drive/Dropbox.
2.  **On Mac**:
    *   Download and unzip the folder.


## 3. Environment Setup
It is highly recommended to use a **Virtual Environment** so you don't mess up your system Python.

1.  **Open Terminal** and navigate to your project folder (assuming synced via OneDrive):
    ```bash
    cd ~/OneDrive/Documents/Antig
    ```
    *(Note: Adjust the path if your OneDrive folder is named differently, e.g., `~/OneDrive - Personal`)*

2.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv venv
    ```

3.  **Activate the Virtual Environment**:
    ```bash
    source venv/bin/activate
    ```
    *(You should see `(venv)` appear at the start of your terminal line)*

## 4. Install Dependencies
Run the following command to install all required libraries (Streamlit, Pandas, etc.):
```bash
pip install -r requirements.txt
```

## 5. Verify Secrets (Crucial!)
The application relies on API keys stored in `.streamlit/secrets.toml`.
1.  Check if the file exists on your Mac:
    ```bash
    ls -a .streamlit/secrets.toml
    ```
2.  **If it allows (synced):** You are good to go.
3.  **If it's missing:** You must create it and copy your keys manually:
    ```bash
    mkdir -p .streamlit
    touch .streamlit/secrets.toml
    open -e .streamlit/secrets.toml
    ```
    Paste your TOML content (keys for Perplexity, Gemini, Finazon) into this file and save.

## 6. Run the Application
With the virtual environment activated, run:
```bash
streamlit run app.py
```
A browser window should automatically open with the application.

---

### Troubleshooting
*   **"Command not found: streamlit"**: Ensure you activated the venv (`source venv/bin/activate`).
*   **API Errors**: Double-check `.streamlit/secrets.toml` content.
*   **Port already in use**: Streamlit will try port 8501 by default. If it's busy, it will use 8502.
