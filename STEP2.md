# Step 2 — Core AI Loop (Text-Only Complaints)

Adds: `Complaint` and `ChatMessage` tables, a Gemini-powered classification call,
`POST /api/chat/message` (complaint flow only for now), `GET /api/complaints`
(Public Inbox), and `GET /api/chat/recents`.

## 1. Get a free Gemini API key

1. Go to **aistudio.google.com** and sign in with any Google account
2. Click **"Get API key"** → **"Create API key"**
3. Copy the key (starts with `AIza...`)

## 2. Install the new dependency

```bash
source venv/bin/activate   # if not already active
pip install -r requirements.txt
```

## 3. Add the key (and model name) to .env

```bash
nano .env
```
- Paste your key as the value of `GEMINI_API_KEY=` (already there as an empty
  placeholder from Step 1)
- Add a new line: `GEMINI_MODEL=gemini-3.5-flash`

Model names get retired regularly, so it lives in `.env` — if you ever see a
`502 ai_call_failed` error mentioning the model, check Google AI Studio for the
current model name and change just this one line, no code edit needed.
Save and exit.

## 4. Run the migration for the two new tables

```bash
flask db migrate -m "add complaints and chat_messages tables"
flask db upgrade
```

Check the migrate output mentions `Detected added table 'complaints'` and
`Detected added table 'chat_messages'` before running upgrade.

## 5. Restart the server

It should auto-reload since `debug=True`, but if anything looks off:
Ctrl+C in the server tab, then `python run.py` again.

## 6. Test the full loop

You'll need a valid access token from Step 1. Log in again to get a fresh one if
your old one expired:

```bash
curl -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"gmail": "secretary@example.com", "password": "SecurePass123"}'
```

Copy the `access_token` value from the response, then use it below (replace
`PASTE_TOKEN_HERE`):

**Raise a complaint:**
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer PASTE_TOKEN_HERE" -d '{"selected_type": "complaint", "text": "There is a water leak near the parking area in Block A, it has been going on for two days"}'
```

Expect a `201` response with `"understood": true`, a `reply` summarizing what was
logged, and a `complaint` object showing the AI-assigned `category` and
`severity`.

**Test the "not understood" fallback** (send clearly unrelated text as a complaint):
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer PASTE_TOKEN_HERE" -d '{"selected_type": "complaint", "text": "write me a poem about the moon"}'
```
Expect `200` with `"understood": false` and a polite "didn't understand" reply —
confirms Edge Case 5 (out-of-scope input) from the brief.

**Confirm it shows up in the Public Inbox:**
```bash
curl http://localhost:5000/api/complaints -H "Authorization: Bearer PASTE_TOKEN_HERE"
```
Expect your logged complaint in the list, with its category/severity.

**Confirm it's also in your chat recents:**
```bash
curl http://localhost:5000/api/chat/recents -H "Authorization: Bearer PASTE_TOKEN_HERE"
```
Expect both your message and the AI's reply as separate entries.

**Test an unauthenticated request is rejected:**
```bash
curl http://localhost:5000/api/complaints
```
Expect `401` — confirms `login_required` is actually enforced, not just present in code.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `503 ai_not_configured` | `GEMINI_API_KEY` empty in `.env`, or server not restarted after editing it |
| `502 ai_call_failed` | Wrong/revoked API key, retired model name, or free-tier quota hit — the `detail` field in the response says which |
| `ModuleNotFoundError: google` | Run `pip install -r requirements.txt` inside the activated venv |

## What's intentionally NOT built yet
- Service requests, Rules Q&A, Committee-actions (`selected_type` values other than
  `complaint` currently return a clean `501 "not built yet"` response)
- Voice input (Whisper) — `original_language` is hardcoded to `"en"` for now
- Role-gated actions (status changes, assignment) — Step 5
- Duplicate detection, escalation — Step 7
