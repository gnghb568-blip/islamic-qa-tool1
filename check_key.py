import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")

if key:
    print(f"تم إيجاد المفتاح! يبدأ بـ: {key[:6]}... وطوله {len(key)} حرف")
else:
    print("المفتاح مش موجود خالص!")