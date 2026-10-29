"""
Translate-on-read. Everything is stored in English; each person reads it in their own preferred language.

How it stays cheap enough for a free Gemini quota:
  * remembered translations (translation_cache) are reused for every reader of the same language
  * everything a page needs is translated in ONE batched call, not one call per item
  * lists are paginated, so only the page being shown is ever translated
  * if Gemini fails, the page still loads in English (it never errors because of translation)
"""
import hashlib
import re

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.translation_cache import TranslationCache
from app.services import gemini
from app.services.gemini_client import GeminiNotConfigured, GeminiCallFailed

LANGUAGE_NAMES = {
    "hi": "Hindi", "or": "Odia", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "mr": "Marathi",
    "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam", "pa": "Punjabi", "ur": "Urdu",
    "as": "Assamese", "ne": "Nepali", "sa": "Sanskrit", "en": "English",
}
LANG_RE = re.compile(r"^[a-z]{2,3}$")


def normalize_lang(code):
    code = (code or "").strip().lower()
    return code if LANG_RE.match(code) else "en"


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, f"the language with ISO 639 code '{code}'")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunks(texts, max_items, max_chars):
    chunk, size = [], 0
    for text in texts:
        if chunk and (len(chunk) >= max_items or size + len(text) > max_chars):
            yield chunk
            chunk, size = [], 0
        chunk.append(text)
        size += len(text)
    if chunk:
        yield chunk


def _remember(source_hash, lang, translated):
    """Store one translation; two requests racing to store the same one is fine (the loser is ignored)."""
    try:
        with db.session.begin_nested():
            db.session.add(TranslationCache(source_hash=source_hash, target_lang=lang, translated_text=translated))
    except IntegrityError:
        pass


def localize_texts(texts, lang):
    """
    texts: list of English strings (None/empty allowed).  lang: the reader's language code.
    Returns (results, meta). results[i] is the translation, or None when there is nothing to show
    (English reader, empty text, or translation unavailable). meta = {"language", "translation"} where
    translation is "not_needed" | "ok" | "partial" | "unavailable".
    """
    lang = normalize_lang(lang)
    if lang == "en":
        return [None] * len(texts), {"language": "en", "translation": "not_needed"}

    wanted = []
    for t in texts:
        if isinstance(t, str) and t.strip() and t not in wanted:
            wanted.append(t)
    if not wanted:
        return [None] * len(texts), {"language": lang, "translation": "ok"}

    hashes = {t: _hash(t) for t in wanted}
    rows = TranslationCache.query.filter(
        TranslationCache.target_lang == lang, TranslationCache.source_hash.in_(list(hashes.values())),
    ).all()
    by_hash = {r.source_hash: r.translated_text for r in rows}

    misses = [t for t in wanted if hashes[t] not in by_hash]
    cfg = current_app.config
    for chunk in _chunks(misses, max(1, cfg["TRANSLATE_BATCH_ITEMS"]), max(1, cfg["TRANSLATE_BATCH_CHARS"])):
        try:
            translated = gemini.translate_texts(chunk, language_name(lang))
        except (GeminiNotConfigured, GeminiCallFailed) as exc:
            current_app.logger.warning("Translation to %s unavailable: %s", lang, exc)
            translated = None
        if translated is None:
            continue                       # leave these in English; nothing wrong gets cached
        for source, result in zip(chunk, translated):
            by_hash[hashes[source]] = result
            _remember(hashes[source], lang, result)
    db.session.commit()

    results = [by_hash.get(hashes[t]) if isinstance(t, str) and t in hashes else None for t in texts]
    resolved = sum(1 for t in wanted if hashes[t] in by_hash)
    status = "ok" if resolved == len(wanted) else ("unavailable" if resolved == 0 else "partial")
    return results, {"language": lang, "translation": status}


def localize_groups(viewer, *groups):
    """
    groups: (items, fields) pairs, where items is a list of dicts. Adds "<field>_local" to every dict (None when
    there is no translation) for readers whose language isn't English, translating EVERYTHING in one batch.
    Returns the meta dict ({"language", "translation"}) to merge into the response.
    """
    slots, texts = [], []
    for items, fields in groups:
        for item in items:
            for field in fields:
                slots.append((item, field))
                texts.append(item.get(field))
    results, meta = localize_texts(texts, viewer.preferred_language)
    if meta["language"] != "en":
        for (item, field), result in zip(slots, results):
            item[f"{field}_local"] = result
    return meta


def to_english(text: str):
    """Best-effort English version of something a person typed (used by search). None if not needed/available."""
    if not text or not text.strip():
        return None
    key = _hash(text)
    row = TranslationCache.query.filter_by(source_hash=key, target_lang="en").first()
    if row:
        return row.translated_text
    try:
        out = gemini.translate_texts([text], "English")
    except (GeminiNotConfigured, GeminiCallFailed):
        return None
    if not out:
        return None
    _remember(key, "en", out[0])
    db.session.commit()
    return out[0]
