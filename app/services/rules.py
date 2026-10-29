from app.models.bylaws_document import BylawsDocument
from app.services.gemini import answer_rules_question

NO_RULEBOOK_MESSAGE = (
    "No society rulebook has been uploaded yet. "
    "Please ask the Secretary or a committee member to upload it."
)
NOT_UNDERSTOOD_MESSAGE = (
    "I didn't understand that as a question about society rules. "
    "Try asking something like \"Can I renovate my balcony on Sunday?\""
)


def latest_rulebook():
    return BylawsDocument.query.order_by(BylawsDocument.version.desc()).first()


def ask_rulebook(question: str) -> dict:
    """
    Shared by the chat flow and POST /api/rules/ask.
    Returns {"status": "answered"|"no_rulebook"|"not_understood", "reply": str}.
    Raises GeminiNotConfigured / GeminiCallFailed (callers turn those into 503 / 502).
    """
    doc = latest_rulebook()
    if doc is None:
        return {"status": "no_rulebook", "reply": NO_RULEBOOK_MESSAGE}

    result = answer_rules_question(doc.content_text, question)
    if result.get("error") == "not_understood":
        return {"status": "not_understood", "reply": NOT_UNDERSTOOD_MESSAGE}
    return {"status": "answered", "reply": result["answer"]}
