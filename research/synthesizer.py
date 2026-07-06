import os
from dotenv import load_dotenv
from groq import Groq
from privacy import redact_sensitive_text
from constants import NOT_FOUND_MESSAGE

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def format_evidence(evidence):
    parts = []

    for i, item in enumerate(evidence, start=1):
        parts.append(
            f"Evidence {i}\n"
            f"Source: {item['source']}\n"
            f"Date: {item['date']}\n"
            f"Confidence: {item['confidence_score']} ({item['confidence_tier']})\n"
            f"Quality: {item['quality']}\n"
            f"Text: {item['text']}"
        )

    return "\n\n".join(parts)


def synthesize_answer(question, sub_questions, evidence, gap_reason):
    safe_question = redact_sensitive_text(question)

    if not evidence:
        return NOT_FOUND_MESSAGE

    evidence_text = format_evidence(evidence)
    sub_question_text = "\n".join(f"- {q}" for q in sub_questions)

    prompt = f"""
You are the Personal Research Agent inside PI Agent.

Answer the user using ONLY the collected personal evidence below.

Rules:
- Do not make up facts.
- If evidence is weak, say that clearly.
- Mention uncertainty when needed.
- Mention conflicts if evidence disagrees.
- Keep the answer concise.
- If there is not enough evidence, say exactly:
"{NOT_FOUND_MESSAGE}"

Original question:
{safe_question}

Research sub-questions:
{sub_question_text}

Gap detector result:
{gap_reason}

Collected evidence:
{evidence_text}

Final answer:
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You synthesize answers from personal evidence only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        max_tokens=700,
    )

    return response.choices[0].message.content.strip()