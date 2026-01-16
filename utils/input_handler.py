import re
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi
from PyPDF2 import PdfReader
import io

def detect_input_type(content):
    """
    Detects if the input is a YouTube URL, a general URL, or raw text.
    """
    content = content.strip()
    
    # YouTube Detection
    if "youtube.com" in content or "youtu.be" in content:
        return "YOUTUBE"
        
    # General URL Detection
    if content.startswith("http://") or content.startswith("https://"):
        return "URL"
        
    return "TEXT"

def extract_transcript(video_url):
    """
    Extracts transcript from a YouTube video.
    """
    try:
        if "v=" in video_url:
            video_id = video_url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[1].split("?")[0]
        else:
            return "Error: Could not extract Video ID."

        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([t['text'] for t in transcript_list])
        return transcript_text
    except Exception as e:
        return f"Error fecthing YouTube transcript: {e}"

def extract_url_text(url):
    """
    Extracts main text from a generic URL using BeautifulSoup.
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Kill all script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        text = soup.get_text()
        
        # Break into lines and remove leading/trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        # Drop blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:10000] # Limit content length
    except Exception as e:
        return f"Error extracting URL text: {e}"

def extract_text_from_pdf(uploaded_file):
    """
    Extracts text from a Streamlit UploadedFile (PDF).
    """
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Error extracting PDF text: {e}"

def process_input(user_input, uploaded_file=None):
    """
    Main entry point for processing input.
    Prioritizes uploaded file, then checks input text type.
    """
    if uploaded_file is not None:
        if uploaded_file.type == "application/pdf":
            return "PDF_CONTENT", extract_text_from_pdf(uploaded_file)
        # Add text file support if needed
    
    if not user_input:
        return "EMPTY", ""
        
    input_type = detect_input_type(user_input)
    
    if input_type == "YOUTUBE":
        return "YOUTUBE_TRANSCRIPT", extract_transcript(user_input)
    elif input_type == "URL":
        return "WEB_CONTENT", extract_url_text(user_input)
    else:
        return "RAW_TEXT", user_input
