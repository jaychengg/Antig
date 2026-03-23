import sys
import os
try:
    import streamlit
    print(f"Streamlit found at: {streamlit.__file__}")
    print(f"Python executable: {sys.executable}")
except ImportError as e:
    print(f"ImportError: {e}")
