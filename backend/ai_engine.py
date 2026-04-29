import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

LANGUAGE_NAMES = {
    'en': 'English', 'hi': 'Hindi', 'ta': 'Tamil', 'te': 'Telugu',
    'kn': 'Kannada', 'ml': 'Malayalam', 'bn': 'Bengali', 'mr': 'Marathi',
    'gu': 'Gujarati', 'pa': 'Punjabi', 'or': 'Odia', 'auto': 'Auto-detect'
}


def translate_to_english(text: str, source_lang: str = 'auto') -> str:
    """Translate text from source_lang to English using Google Translate (free tier)."""
    if source_lang == 'en':
        return text
    try:
        from deep_translator import GoogleTranslator
        src = 'auto' if source_lang == 'auto' else source_lang
        translated = GoogleTranslator(source=src, target='en').translate(text)
        return translated or text
    except Exception as e:
        print(f"[ai_engine] Translation error: {e}")
        return text  # graceful fallback — return original


def generate_formal_letter(complaint_text: str, location: str, is_emergency: bool) -> str:
    """Generate a formal complaint letter. Uses Gemini if key available, else template."""
    if GEMINI_API_KEY:
        result = _generate_with_gemini(complaint_text, location, is_emergency)
        if result:
            return result
    return _generate_with_template(complaint_text, location, is_emergency)


def _generate_with_gemini(complaint_text: str, location: str, is_emergency: bool) -> str:
    """Call Google Gemini API to generate a formal complaint letter."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')

        priority = "URGENT / EMERGENCY" if is_emergency else "Normal"
        prompt = f"""
You are a professional complaint letter writer helping vulnerable communities.
Write a formal, polite complaint letter to the relevant authority based on the following details.

Complaint Details:
- Complaint Text: {complaint_text}
- Location: {location}
- Priority: {priority}
- Date: {datetime.now().strftime('%d %B %Y')}

Instructions:
1. Format as a proper letter with Subject, Body, and closing
2. Be clear, concise, and professional
3. Include the location prominently
4. If marked EMERGENCY, add urgency politely
5. Do NOT add fictional names or contact details
6. End with "Submitted via Smart Grievance Redressal System"

Write ONLY the letter content, nothing else.
"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"[ai_engine] Gemini error: {e}")
        return None


def _generate_with_template(complaint_text: str, location: str, is_emergency: bool) -> str:
    """Rule-based formal letter template (zero API cost fallback)."""
    date_str = datetime.now().strftime('%d %B %Y')
    priority_line = "\n⚠️  URGENT / EMERGENCY — Immediate action is requested.\n" if is_emergency else ""

    return f"""Date: {date_str}

To,
The Concerned Authority / NGO Representative,
{location}

Subject: Formal Complaint Regarding Community Issue — {'URGENT' if is_emergency else 'Requires Attention'}

Respected Sir/Madam,
{priority_line}
I am writing to bring the following matter to your kind attention. The complaint was submitted by a community member through the Smart Grievance Redressal System and has been automatically processed and forwarded to the appropriate authority.

Complaint Description:
{complaint_text}

Location of Issue:
{location}

I kindly request you to look into this matter at the earliest and take appropriate action. The complainant is eagerly awaiting a response and resolution.

Thanking you in anticipation of a prompt response.

Yours faithfully,
[Submitted Anonymously via Smart Grievance Redressal System]
Date of Submission: {date_str}
"""
