import requests
from urllib.parse import urlparse
import os
from datetime import datetime

def Download_File(url, file_path):
    # Validate URL
    if not url or not url.strip():
        raise ValueError("URL cannot be empty")
    
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        raise ValueError(f"Invalid URL scheme: {url}")
    
    # Parse URL
    parsed_url = urlparse(url)
    # Get path part
    path = parsed_url.path
    # Extract filename
    filename = os.path.basename(path)
    print("Original filename:----", filename)
    # Split filename and extension
    name, ext = os.path.splitext(filename)

    # Add timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{name}_{timestamp}{ext}"
    print("filename:----", filename)

    save_path = os.path.join(file_path, filename)
    if os.path.exists(save_path):
        print("Already downloaded this file")
        return save_path

    r = requests.get(url)
    r.raise_for_status()
    with open(save_path, 'wb') as f:
        f.write(r.content)
    print(f"saved successfully file- {save_path}")
    return save_path

