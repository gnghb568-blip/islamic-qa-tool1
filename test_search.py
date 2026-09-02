import os
import requests
from dotenv import load_dotenv

load_dotenv()

SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

url = "https://www.googleapis.com/customsearch/v1"
params = {
    "key": SEARCH_API_KEY,
    "cx": SEARCH_ENGINE_ID,
    "q": "حكم صيام يوم الشك",
    "num": 3,
}

response = requests.get(url, params=params, timeout=10)
print(response.json())