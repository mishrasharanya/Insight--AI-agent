# embedding_client.py = lightweight Gemini embeddings client

import os
from google import genai
from google.genai import types

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768

_client = None


def get_genai_client():
    global _client

    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY is not set. "
                "Create one in Google AI Studio and add it to your environment."
            )

        _client = genai.Client(api_key=api_key)

    return _client


def embed_text(text):
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    client = get_genai_client()

    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSION
        ),
    )

    return result.embeddings[0].values