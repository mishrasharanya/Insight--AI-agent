import random


GREETINGS = [
    "Hello! How can I help you today?",
    "Hi! What would you like to know?",
    "Hey! How can I assist you today?",
    "Good to see you again! What can I help you with?",
]

THANKS = [
    "You're welcome!",
    "Happy to help!",
    "Anytime!",
    "Glad I could help!",
]


def respond(text: str):
    text = text.lower().strip()

    greetings = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "good morning",
        "good afternoon",
        "good evening",
        "yo",
        "sup",
        "what's up",
        "whats up",
    }

    thanks = {
        "thanks",
        "thank you",
        "ty",
        "thanks!",
        "thank you!",
    }

    if text in greetings:
        return random.choice(GREETINGS)

    if text in thanks:
        return random.choice(THANKS)

    return None