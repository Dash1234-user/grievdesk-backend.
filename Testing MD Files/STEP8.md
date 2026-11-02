# Step 8 — Translate-on-read, Search, Inbox filters and paging

Everything is still **stored in English**. Each person now **reads** it in their own preferred language
(`preferred_language`, set in Profile or at registration, e.g. `hi`, `or`).

## How the response looks
| Reader's language | What you get |
|---|---|
| English (`en`) | Exactly what you had before. No `*_local` fields, `"translation": "not_needed"`. |
| Anything else | The English field **plus** a `<field>_local` sibling, e.g. `translated_text` + `translated_text_local`. |

Every translated response also carries `"language"` and `"translation"`: `ok`, `partial` (some texts failed) or `unavailable`
(Gemini failed: the page still loads, in English, with `*_local: null`). **Frontend rule: show `x_local ?? x`**, and keep `x`
for a "show original" toggle.

Translated: complaint text + resolution notes + timeline notes, service request descriptions, announcements (title + message),
notifications, My Tickets, the bot's chat replies (`reply_local`, English `reply` is kept) and the assistant messages in a Recents thread.
Not translated: what a person typed or said, names, and labels like `category` / `status` (the frontend translates those).

## Why it won't eat your Gemini quota
- Remembered translations (`translation_cache`) are reused for every reader of that language. A new sentence is translated once, ever.
- A whole page is **one batched call**, not one per item.
- Lists are paged, so only the page on screen is translated.
- If Gemini is down, nothing breaks and nothing wrong is remembered; the next read retries.

## Paging and filters (needed so translation stays cheap)
| Endpoint | Paging | Filters |
|---|---|---|
| `GET /api/complaints` | `?limit=` (default 20, max 100) `?offset=`, returns `total` | `?status=` `?category=` `?severity=` `?block=` |
| `GET /api/announcements` | the *General* list is paged, *Pinned* is always complete (`general_total`) | |
| `GET /api/notifications/me` | default 30, max 100; `unread_count` still counts all | |

`?block=` never reveals where an anonymous complaint came from: other residents only get matches they're allowed to identify.

## Search: `GET /api/search?q=...` (2-100 characters, `?limit=` per group, default 10)
Searches complaints (the English text everyone can already read in the Public Inbox), service requests (**yours**; staff see all),
announcements, and the rulebook (returns the matching paragraph with its `section` number). Case-insensitive; `%` and `_` are plain
characters. If you type in another script, the query is also translated to English (`query_english`), once, then remembered.
It never searches the hidden original wording of anyone's complaint.

## Decisions I made that you didn't specify — change any you disagree with
1. English is always the stored truth; the translation is added next to it, never in place of it.
2. The bot's reply is translated **when it is sent**, which costs one extra Gemini call per message for non-English users (cached afterwards).
3. The Public Inbox now defaults to **20 per page**; the frontend must page.
4. Search covers complaints, service requests, announcements and rules, but not the directory or notifications.
5. `translation_cache` is never pruned automatically. It only holds text and is tiny; you can empty it any time and it refills itself.

## 1. Apply
Copy the zip into `grievdesk-backend` (Merge `app`, Replace conflicts), then:
```bash
flask db migrate -m "translation cache"
flask db upgrade
```
The output must show `Detected added table 'translation_cache'`. No pip install. Restart `python run.py`.

## 2. Test (`STOKEN`, `RTOKEN` from before)
**Make your resident a Hindi reader, then read the Public Inbox**
```bash
curl -X PUT http://localhost:5000/api/users/me -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"preferred_language": "hi"}'
curl "http://localhost:5000/api/complaints?limit=5" -H "Authorization: Bearer $RTOKEN"
```
Read `translated_text_local`. **Is the Hindi correct and natural?** Run the same command again: it should be instant (remembered).
Watch the server tab: a Gemini call happens only the first time.

**The bot answers in Hindi too**
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "complaint", "text": "The lift in Block B has been stuck since morning"}'
curl http://localhost:5000/api/announcements -H "Authorization: Bearer $RTOKEN"
curl http://localhost:5000/api/notifications/me -H "Authorization: Bearer $RTOKEN"
```
**Now the important one: switch to Odia** (`"or"`) and repeat the first inbox command. **You can judge Odia; I can't.**
Send me what's wrong, if anything. When done set it back to `"en"`.

**Search and filters**
```bash
curl "http://localhost:5000/api/search?q=leak" -H "Authorization: Bearer $RTOKEN"
curl -G http://localhost:5000/api/search --data-urlencode "q=पानी" -H "Authorization: Bearer $RTOKEN"
curl "http://localhost:5000/api/search?q=quiet" -H "Authorization: Bearer $RTOKEN"
curl "http://localhost:5000/api/complaints?status=new&category=Plumbing&limit=5" -H "Authorization: Bearer $STOKEN"
```
The Hindi search shows a `query_english`; `quiet` finds a rulebook section (upload a rulebook first if you haven't).

## Honest limits
- **Translation quality is unverified**, especially Odia. The prompt tells Gemini to keep numbers, names and ids unchanged, but only you can judge the result.
- The first read in a new language costs one Gemini call (a second or two). For your viva, open each page once in each language beforehand so the cache is warm.
- Search is plain "contains": no typo tolerance, stemming or ranking. Fine at society scale.
- Labels such as `category` and `status` arrive as English codes; the frontend must translate those itself.
- A search or read in a language right after Gemini's daily free quota is used up will simply show English.
