DISCLAIMER = (
    "\n\n---\n"
    "**Disclaimer.** This information is for educational purposes only and is not a "
    "substitute for professional medical advice, diagnosis, or treatment. Always seek "
    "the advice of a qualified clinician with any questions you may have regarding a "
    "medical condition. If you think you may have a medical emergency, call your local "
    "emergency number immediately."
)


def with_disclaimer(text: str) -> str:
    if DISCLAIMER.strip() in text:
        return text
    return text.rstrip() + DISCLAIMER
