import os
import json
from dotenv import load_dotenv
from groq import Groq

from privacy import redact_sensitive_text

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

groq_client = Groq(api_key=GROQ_API_KEY)


def create_research_plan(question):
    safe_question = redact_sensitive_text(question)

    prompt = f"""
You are the Research Planner for a Personal Intelligence Agent.

Break the user's question into 2-5 focused search queries over personal memory.

User question:
{safe_question}

Return ONLY valid JSON in this format:
{{
  "sub_questions": [
    "search query 1",
    "search query 2"
  ]
}}
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=500,
    )

    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
        sub_questions = data.get("sub_questions", [])
        if sub_questions:
            print("[Research Planner]", sub_questions)
            return sub_questions
    except json.JSONDecodeError:
        pass

    return [safe_question]