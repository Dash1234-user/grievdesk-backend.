# Step 5 — Role-Gated Actions

| Area | New endpoints |
|---|---|
| Ticket handling | `PATCH /api/complaints/<id>/status`, `PATCH /api/complaints/<id>/assign`, `PATCH /api/service-requests/<id>/status`, `GET /api/service-requests/<id>`; `GET /api/complaints/<id>` now includes a `timeline` |
| People & roles | `GET /api/users` (directory, `?status=pending` for the Secretary's approval queue), `PATCH /api/users/<id>/promote-to-committee`, `/demote`, `/transfer-secretary` |
| Anonymity | chat complaint field `anonymous` (true/false) |

## What changed in behaviour
- **Roles are read from the database on every request**, not from the login token. Promote, demote or
  transfer someone and it applies on their very next request; a token that merely *claims* a role is ignored;
  an account that is no longer approved stops working immediately.
- **Anonymous complaints** hide flat/block from other residents. The owner and committee/secretary see them;
  only committee/secretary also get `submitted_by` (so they can resolve it). Voice recordings follow the same rule.
- **Status changes and assignments** are recorded in a new `ticket_events` table (the timeline) and the person who
  raised the ticket gets a private notification. You are not notified about your own changes.
- Tickets can only be **assigned** to the Secretary or a committee member.
- **Transfer of the Secretary title** needs `{"confirm": true}`. The outgoing Secretary becomes a committee member.
- `GET /api/users`: everyone sees name, flat, block and role. Phone numbers appear only if the owner set `share_phone`.
  Emails and approval status are for committee/secretary (and you can see your own).

## Decisions I made that you didn't specify — change any you disagree with
1. **Only the Secretary can demote** a committee member. Committee members are equals, so letting them remove
   each other would let a few lock the rest out. It's also how a new committee takes over after elections:
   demote the old members, promote the new ones.
2. Outgoing Secretary becomes **committee**, not a plain resident.
3. Transfer needs the explicit `confirm` flag.

## 1. Apply
Copy the zip into `grievdesk-backend` (Merge `app`, Replace conflicts), then in the venv tab:
```bash
flask db migrate -m "add ticket events"
flask db upgrade
```
The migrate output must say `Detected added table 'ticket_events'`. Restart `python run.py`.
(Whisper/OpenAI is gone: nothing to set; you can delete `OPENAI_API_KEY` and `STT_PROVIDER` from `.env`.)

## 2. Test (single-line commands, curl tab)
A helper so you don't copy tokens by hand:
```bash
login() { curl -s -X POST http://localhost:5000/api/auth/login -H "Content-Type: application/json" -d "{\"gmail\": \"$1\", \"password\": \"$2\"}" | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])"; }
```
```bash
STOKEN=$(login secretary@example.com SecurePass123)
RTOKEN=$(login resident1@example.com ResidentPass123)
```

**Two more residents (to test roles), then the approval queue**
```bash
curl -X POST http://localhost:5000/api/auth/register -H "Content-Type: application/json" -d '{"role": "resident", "name": "Priya", "phone": "9222222222", "flat_no": "C-303", "block_no": "C", "gmail": "priya@example.com", "preferred_language": "en", "password": "Pass12345"}'
curl -X POST http://localhost:5000/api/auth/register -H "Content-Type: application/json" -d '{"role": "resident", "name": "Dev", "phone": "9333333333", "flat_no": "D-404", "block_no": "D", "gmail": "dev@example.com", "preferred_language": "en", "password": "Pass12345"}'
curl "http://localhost:5000/api/users?status=pending" -H "Authorization: Bearer $RTOKEN"
curl "http://localhost:5000/api/users?status=pending" -H "Authorization: Bearer $STOKEN"
```
The resident gets `403`; the Secretary sees Priya and Dev with their ids. Approve both (use their ids), then log in:
```bash
curl -X PATCH http://localhost:5000/api/users/PRIYA_ID/approve -H "Authorization: Bearer $STOKEN"
curl -X PATCH http://localhost:5000/api/users/DEV_ID/approve -H "Authorization: Bearer $STOKEN"
PTOKEN=$(login priya@example.com Pass12345)
DTOKEN=$(login dev@example.com Pass12345)
curl http://localhost:5000/api/users -H "Authorization: Bearer $DTOKEN"
```
In the directory, other people's `phone` and `gmail` must be hidden.

**Anonymous complaint: who sees what**
```bash
curl -X POST http://localhost:5000/api/chat/message -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"selected_type": "complaint", "anonymous": true, "text": "Someone keeps parking in my reserved slot in Block B"}'
curl http://localhost:5000/api/complaints -H "Authorization: Bearer $DTOKEN"
curl http://localhost:5000/api/complaints -H "Authorization: Bearer $STOKEN"
```
Dev must see `flat_no: null` and no `submitted_by`; the Secretary sees both. Note the new complaint's `id` (called `ID` below).

**Status, notification, timeline, assignment**
```bash
curl -X PATCH http://localhost:5000/api/complaints/ID/status -H "Content-Type: application/json" -H "Authorization: Bearer $DTOKEN" -d '{"status": "in_progress"}'
curl -X PATCH http://localhost:5000/api/complaints/ID/status -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"status": "in_progress"}'
curl -X PATCH http://localhost:5000/api/complaints/ID/status -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"status": "resolved", "resolution_notes": "Spoke to the neighbour, slot is clear"}'
curl http://localhost:5000/api/notifications/me -H "Authorization: Bearer $RTOKEN"
curl http://localhost:5000/api/complaints/ID -H "Authorization: Bearer $DTOKEN"
curl -X PATCH http://localhost:5000/api/complaints/ID/assign -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"assigned_to": DEV_ID}'
```
Dev's attempt is `403`. The resident (owner) gets a private update notification. The timeline shows both
changes. Assigning to Dev (a resident) fails with `invalid_assignee` until Dev is committee.

**Promote / demote — and watch an old token change power instantly**
```bash
curl -X PATCH http://localhost:5000/api/users/PRIYA_ID/promote-to-committee -H "Authorization: Bearer $STOKEN"
PTOKEN=$(login priya@example.com Pass12345)
curl -X PATCH http://localhost:5000/api/users/DEV_ID/promote-to-committee -H "Authorization: Bearer $PTOKEN"
curl -X PATCH http://localhost:5000/api/complaints/ID/status -H "Content-Type: application/json" -H "Authorization: Bearer $DTOKEN" -d '{"status": "escalated"}'
curl -X PATCH http://localhost:5000/api/users/PRIYA_ID/approve -H "Authorization: Bearer $PTOKEN"
curl -X PATCH http://localhost:5000/api/users/DEV_ID/demote -H "Authorization: Bearer $PTOKEN"
curl -X PATCH http://localhost:5000/api/users/DEV_ID/demote -H "Authorization: Bearer $STOKEN"
curl -X PATCH http://localhost:5000/api/complaints/ID/status -H "Content-Type: application/json" -H "Authorization: Bearer $DTOKEN" -d '{"status": "new"}'
```
Expected: promote by committee `200`; Dev's **old** token (made while he was a resident) now changes status `200`;
Priya approving a registration `403` (Secretary-only); Priya demoting `403`; Secretary demoting `200`;
Dev's same token is then `403` again.

**Transfer the Secretary title (and back)**
```bash
curl -X PATCH http://localhost:5000/api/users/PRIYA_ID/transfer-secretary -H "Authorization: Bearer $STOKEN"
curl -X PATCH http://localhost:5000/api/users/PRIYA_ID/transfer-secretary -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"confirm": true}'
curl -X PATCH http://localhost:5000/api/users/DEV_ID/approve -H "Authorization: Bearer $STOKEN"
curl -X PATCH http://localhost:5000/api/users/SECRETARY_ID/transfer-secretary -H "Content-Type: application/json" -H "Authorization: Bearer $PTOKEN" -d '{"confirm": true}'
```
First call `400 confirmation_required`; second `200`. Your old Secretary token can no longer approve, while
Priya's old token now can. Last command hands the title back (`SECRETARY_ID` is 1 unless you changed it).

## Known gaps (next)
- Step 6: Profile (`/api/users/me`), Dues listing + mark-paid, announcement pin/edit/delete, Amenity booking,
  My Tickets listing, translate-on-read.
- Step 7: weekly chat cleanup, auto-escalation of stale tickets (it will write to `ticket_events` as "system"),
  duplicate detection.
