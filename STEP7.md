# Step 7 — Duplicate detection, auto-escalation, weekly chat cleanup

| Feature | How it works |
|---|---|
| **Duplicate detection** | When a complaint is filed, if an open original with the **same category** from the **same block** was reported in the last **48 h**, the new one is linked to it (`duplicate_of`). It stays its own ticket and stays visible to everyone; the original shows `reports_count` and (on its detail) `linked_reports`. "Other" never matches. |
| **Status follows the original** | Staff update the original and every linked report moves with it, and each reporter gets their own private notification. |
| **Fix wrong links** | `PATCH /api/complaints/<id>/duplicate` with `{"duplicate_of": 12}` or `{"duplicate_of": null}` (committee/secretary). |
| **Auto-escalation** | Any complaint still `new` after **5 days** becomes `escalated`. The person who raised it is told; every committee member and the Secretary gets **one digest** listing what was escalated. Recorded in the timeline as by `system`. Duplicates follow their original. Tickets already `in_progress` never escalate (someone is on it). |
| **Chat cleanup** | Deletes chat **transcripts** older than 7 days. Nothing else: complaints, tickets, dues, announcements, notifications and voice notes are untouched. |
| **Recents** | `GET /api/chat/recents` now returns **threads** (title, type, message count, last activity), newest first, last 7 days only. `GET /api/chat/recents/<session_id>` returns one thread; send that `session_id` with `POST /api/chat/message` to continue it. **This changes the old response shape.** |
| **Job tracking** | Every run is recorded (`job_runs`), including failures. `flask jobs status` shows the last run of each. |

## Decisions I made that you didn't specify — change any you disagree with
1. **Duplicate rule is category + block + 48 h, as in your design.** It is crude: two different plumbing problems in one block within 48 h get linked.
   That is why staff can un-link. If wrong links show up in practice, the upgrade is letting Gemini compare the two texts.
2. **Escalation only for complaints still `new`**, threshold 5 days (your example). Service requests don't escalate.
3. **Schedule:** escalation daily at **09:00**, cleanup **Sundays 00:00**, society time. Both thresholds and the 48 h window are `.env` settings
   (`ESCALATION_DAYS`, `DUPLICATE_WINDOW_HOURS`, `CHAT_RETENTION_DAYS`).
4. **Two ways to run the jobs:** the `flask jobs ...` commands (use with cron), or `ENABLE_SCHEDULER=true` to run them inside `python run.py`. It is **off by default**.

## 1. Apply
Copy the zip into `grievdesk-backend` (Merge `app`, Replace conflicts). Then in the venv tab:
```bash
pip install -r requirements.txt
flask db migrate -m "job runs and system notifications"
flask db upgrade
```
`pip` installs APScheduler. The migrate output must show the new table `job_runs` **and** a change to `notifications.created_by`
(it now allows NULL because system messages have no human author). Restart `python run.py`.

## 2. Test
**Duplicate detection** (send the exact same sentence twice so Gemini picks the same category both times)
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "complaint", "text": "There is a water pipe leaking in the Block B corridor"}'
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "complaint", "text": "There is a water pipe leaking in the Block B corridor"}'
```
The second reply says it was linked to the first, and its `duplicate_of` is the first complaint's id. Then, as the Secretary:
```bash
curl http://localhost:5000/api/complaints/FIRST_ID -H "Authorization: Bearer $STOKEN"
curl -X PATCH http://localhost:5000/api/complaints/FIRST_ID/status -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"status": "in_progress"}'
curl http://localhost:5000/api/complaints/SECOND_ID -H "Authorization: Bearer $STOKEN"
```
The first shows `reports_count: 2` and `linked_reports`; the status call answers `linked_reports_updated: 1`; the second complaint is now `in_progress` too.

**Escalation** (backdate a complaint instead of waiting 5 days; pick a complaint that is still `new`)
```bash
sudo -u postgres psql -d grievdesk -c "select id, status, created_at from complaints order by id;"
sudo -u postgres psql -d grievdesk -c "UPDATE complaints SET created_at = now() - interval '6 days' WHERE id = ID AND status = 'new';"
flask jobs escalate
curl http://localhost:5000/api/complaints/ID -H "Authorization: Bearer $STOKEN"
curl http://localhost:5000/api/notifications/me -H "Authorization: Bearer $STOKEN"
```
Expect `escalated: 1`, a timeline entry by `system`, and one digest notification for the Secretary. Run `flask jobs escalate` again: `escalated: 0`.

**Cleanup + Recents**
```bash
curl http://localhost:5000/api/chat/recents -H "Authorization: Bearer $RTOKEN"
sudo -u postgres psql -d grievdesk -c "UPDATE chat_messages SET created_at = now() - interval '8 days' WHERE id IN (SELECT id FROM chat_messages ORDER BY id LIMIT 4);"
curl http://localhost:5000/api/chat/recents -H "Authorization: Bearer $RTOKEN"
flask jobs cleanup-chats
curl http://localhost:5000/api/complaints -H "Authorization: Bearer $STOKEN"
flask jobs status
```
The old threads vanish from Recents immediately; the job reports how many rows it deleted; **all complaints are still there**.

**Scheduler (optional)** — add `ENABLE_SCHEDULER=true` to `.env`, restart, and look for the log line `Scheduler started: chat cleanup Sundays 00:00, escalation daily 09:00`.
For a real deployment use cron instead, one line per job (edit with `crontab -e`, fix the paths):
```
0 9 * * * cd /home/you/grievdesk-backend && venv/bin/flask jobs escalate
0 0 * * 0 cd /home/you/grievdesk-backend && venv/bin/flask jobs cleanup-chats
```

## Honest limits
- The "two runs at once" protection in escalation (`SKIP LOCKED`) is PostgreSQL-only; my tests run on SQLite, so the idempotency is tested but the lock is not.
  Don't enable the in-process scheduler under several server worker processes; use cron there.
- A voice note is kept as long as its complaint exists. There is still no retention policy for voice recordings.
- **Still not built on the backend:** (1) **translate-on-read** (showing each resident complaints/announcements/notifications in their own preferred language),
  (2) the **search** behind your sidebar's search icon. Both change API responses, so they are better done before the frontend.
