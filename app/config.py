import os
from dotenv import load_dotenv

load_dotenv()

VIZARD_API_KEY = os.getenv("VIZARD_API_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
INTRO_DIR = os.path.join(DATA_DIR, 'intro')
OUTRO_DIR = os.path.join(DATA_DIR, 'outro') 
MERGE_DIR = os.path.join(DATA_DIR, 'merge') 

cloud_name = os.getenv("CLOUD_NAME")
api_key = os.getenv("API_KEY")
api_secret = os.getenv("API_SECRET")

BACKEND_URL = "http://65.49.81.27:5000/api/v1"