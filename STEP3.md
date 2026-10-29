# Step 3 — Service Requests, Rules Q&A, Committee Actions

All four chat types now work. The user still picks the type first; nothing guesses intent.

| `selected_type` | What happens |
|---|---|
| `complaint` | (Step 2, unchanged) |
| `service` | Gemini structures it → saved to `service_requests` |
| `rules` | Answers from the latest uploaded rulebook, nothing saved |
| `committee_action` | **Secretary/committee only.** `action` = `announcement` or `dues_reminder` |

Request shapes for `POST /api/chat/message`:

| Type | Body |
|---|---|
| service | `{"selected_type":"service","text":"..."}` |
| rules | `{"selected_type":"rules","text":"..."}` |
| announcement | `{"selected_type":"committee_action","action":"announcement","text":"rough note","pin":true}` (`pin` optional) |
| dues reminder | `{"selected_type":"committee_action","action":"dues_reminder","flat_no":"B-204","block_no":"B","text":"remind them about September dues"}` |

Also added: `POST /api/rules/upload`, `POST /api/rules/ask`, `GET /api/announcements`,
`GET /api/notifications/me`, `GET /api/service-requests`, `POST /api/dues`, and
`PATCH /api/users/<id>/approve` (Secretary only — you need it to approve your test resident).

## 1. Apply the files
Copy the zip contents into `grievdesk-backend`, choosing **Merge** for `app` and **Replace**
for conflicts (tick "apply to all"), same as Step 2.

## 2. Install, migrate, restart
```bash
pip install -r requirements.txt
flask db migrate -m "add service requests, rulebook, announcements, dues, notifications"
flask db upgrade
```
The migrate output should list 5 added tables: `service_requests`, `bylaws_document`,
`announcements`, `dues`, `notifications`. Then restart `python run.py` in the server tab.

## 3. Test (curl tab, single-line commands)

**Tokens — secretary and resident:**
```bash
STOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"gmail": "secretary@example.com", "password": "SecurePass123"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```
Approve your pending resident (it was most likely user id 2):
```bash
curl -X PATCH http://localhost:5000/api/users/2/approve -H "Authorization: Bearer $STOKEN"
```
If that says `user_not_found`, list ids with:
`sudo -u postgres psql -d grievdesk -c "select id, gmail, flat_no, block_no, approval_status from users;"`
```bash
RTOKEN=$(curl -s -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d '{"gmail": "resident1@example.com", "password": "ResidentPass123"}' | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

**A. Service request (as resident)** — expect `201`, `service_type: plumber`:
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "service", "text": "My kitchen tap is leaking, I need a plumber tomorrow morning"}'
```
Wrong-type check — expect `understood: false`:
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "service", "text": "write me a poem"}'
```

**B. Rulebook** — create a sample file, then upload it as the Secretary:
```bash
printf 'Society Rules\n1. The gym is open 5am to 11pm daily.\n2. Renovation work is allowed Monday to Saturday, 9am to 5pm. No work on Sundays.\n3. Quiet hours are 10pm to 6am.\n' > rules.txt
curl -X POST http://localhost:5000/api/rules/upload -H "Authorization: Bearer $STOKEN" -F "file=@rules.txt"
```
Expect `201`, `version: 1`. The same upload as the resident must give `403`:
```bash
curl -X POST http://localhost:5000/api/rules/upload -H "Authorization: Bearer $RTOKEN" -F "file=@rules.txt"
```
Ask questions as the resident:
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "rules", "text": "Can I do balcony renovation on Sunday?"}'
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "rules", "text": "Is the swimming pool open on holidays?"}'
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "rules", "text": "My tap is leaking"}'
```
Expect: a "No, not on Sundays" style answer; a plain "the rulebook doesn't cover that"
(it must NOT invent a pool rule); and a "didn't understand that as a rules question".

**C. Announcement (Secretary posts, resident reads)**
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"selected_type": "committee_action", "action": "announcement", "pin": true, "text": "water tank cleaning this friday 9:30 to 2, water supply will be off, store water"}'
curl http://localhost:5000/api/announcements -H "Authorization: Bearer $RTOKEN"
curl http://localhost:5000/api/notifications/me -H "Authorization: Bearer $RTOKEN"
```
Check the polished notice only uses details you gave (no invented dates/names). The resident
trying the same announcement command must get `403`:
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "committee_action", "action": "announcement", "text": "free pizza for all"}'
```

**D. Dues + targeted reminder**
```bash
curl -X POST http://localhost:5000/api/dues -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"flat_no": "B-204", "block_no": "B", "month": "2026-09", "amount": 2500, "due_date": "2026-09-10"}'
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"selected_type": "committee_action", "action": "dues_reminder", "flat_no": "B-204", "block_no": "B", "text": "remind them about the September dues"}'
curl http://localhost:5000/api/notifications/me -H "Authorization: Bearer $RTOKEN"
curl http://localhost:5000/api/notifications/me -H "Authorization: Bearer $STOKEN"
```
The resident's list must contain the reminder; the Secretary's list must NOT (it is private to B-204).

## Known gaps (intentional)
- Voice input and translate-on-read for announcements/notifications: Step 4 and the frontend.
- Permission decorators still trust the `role` inside the token; a promoted/demoted user keeps the
  old role until they log in again. The chat route already reads the role from the database; Step 5
  moves the decorators to do the same when promotion is built.
- Pin/unpin, edit and delete announcements, full Dues listing and mark-paid: Steps 5–6.
