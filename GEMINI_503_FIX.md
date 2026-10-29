# Gemini overload fix (retry + automatic model fallback)

Gemini answered `503 UNAVAILABLE - high demand`. Every Gemini call (typed AND voice) now goes through
`app/services/gemini_client.py`:

| What Gemini says | What happens |
|---|---|
| 500 / 502 / 503 / 504, timeout, dropped connection | wait 1.5 s, retry the same model once, then try the next model |
| 429 (this model's quota used up) or 404 (model retired) | go straight to the next model |
| 400 / 401 / 403 (bad key or bad request) | fail immediately (retrying can't fix it) |
| everything failed | clean `502 ai_call_failed`, nothing saved; `detail` lists what each model said |

Worst case is 6 attempts, so a resident waits seconds, not minutes. The server log prints a WARNING whenever
a backup model answered, so you can see what is happening.

## Apply
Copy the zip into `grievdesk-backend` (Merge `app`, Replace conflicts). No pip install, no migration. Edit `.env`:
```
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODELS=gemini-3.1-flash-lite
```
Restart `python run.py`, then retry your complaint.

## While 3.5 is overloaded
Put the lighter model FIRST so every request doesn't wait through a failed attempt:
```
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_FALLBACK_MODELS=gemini-3.5-flash
```
Names change. If you see `404` in the error `detail`, open aistudio.google.com, check the model list for your key,
and fix the name here. Community reports say gemini-3.5-flash's free tier is only ~20 requests/day (I could not
confirm that from Google), so heavy testing can use it up; the fallback covers that too (a 429).
After switching to a lighter model, re-test your Odia and Hindi voice notes: smaller models can be weaker.
