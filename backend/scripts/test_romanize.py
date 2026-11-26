from google import genai
from google.genai import types
from app.config import settings

def test_romanize():
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    prompt = """You are an expert in Urdu, Hindi, Roman Urdu, and Hinglish.
Convert the following transcript words into Roman Urdu / Hinglish (Latin English letters only).
Keep the exact same number of items and the exact start and end timestamps. Every word MUST be in English/Latin letters.
Input words:
[
  {"word": "یہ", "start": 1.0, "end": 1.4},
  {"word": "بہت", "start": 1.4, "end": 1.8},
  {"word": "اچھا", "start": 1.8, "end": 2.3},
  {"word": "है", "start": 2.3, "end": 2.6},
  {"word": "क्या", "start": 2.6, "end": 3.0},
  {"word": "बात", "start": 3.0, "end": 3.4},
  {"word": "hai!", "start": 3.4, "end": 3.8}
]

Return strictly a JSON list of objects with keys: word, start, end.
"""
    res = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )
    print("ROMANIZED OUTPUT:")
    print(res.text)

if __name__ == "__main__":
    test_romanize()
