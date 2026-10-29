# Step 6 — Profile, Dues, Announcements, Amenity Booking, My Tickets

| Section | Endpoints |
|---|---|
| Profile | `GET /api/users/me`, `PUT /api/users/me` |
| Dues | `GET /api/dues/me` (own only), `GET /api/dues` (staff, filters), `PATCH /api/dues/<id>/mark-paid`, `POST /api/dues/<id>/remind` (AI-drafted) |
| Announcements | `PATCH /api/announcements/<id>/pin`, `PATCH /api/announcements/<id>` (edit), `DELETE /api/announcements/<id>` |
| Notifications | `PATCH /api/notifications/<id>/read`, `POST /api/notifications/read-all`; list now has `unread_count` |
| Amenities | `GET/POST /api/amenities`, `GET /api/amenities/<id>/availability?date=` |
| Bookings | `POST /api/amenity-bookings`, `GET /api/amenity-bookings/me`, `GET /api/amenity-bookings` (staff), `DELETE /api/amenity-bookings/<id>` |
| My Tickets | `GET /api/my-tickets` (your complaints + service requests, each with a timeline) |

## Decisions I made that you didn't specify — change any you disagree with
1. **Moving to another flat/block** needs `confirm_reapproval: true`, sends you back to the Secretary for approval and
   logs you out until it's given. Otherwise anyone could claim any flat after being approved. The Secretary is exempt.
2. **Booking rules** (in `.env`, no code change): max **4 hours** per booking, up to **30 days** ahead, nothing in the past,
   judged in `SOCIETY_TIMEZONE` (default `Asia/Kolkata`). Back-to-back bookings (6-7 then 7-8) are allowed.
3. **Cancelled bookings are kept** as history and free the slot. If staff cancel yours, you get a private notification.
4. **Announcements are created only by the AI chat** (as you wanted); the new endpoints only pin/edit/delete existing ones.
5. **Read state is per person.** A broadcast announcement read by one resident stays unread for everyone else.
6. Passwords must be at least **8 characters** (now also enforced at registration).
7. A reminder from `/remind` covers **all** of that person's unpaid months, not just the one you pointed at.

## 1. Apply
Copy the zip into `grievdesk-backend` (Merge `app`, Replace conflicts), then:
```bash
flask db migrate -m "add amenities, bookings, notification reads"
flask db upgrade
```
The migrate output must list **3** added tables: `amenities`, `amenity_bookings`, `notification_reads`. Restart `python run.py`.
No pip install needed.

## 2. Test (`STOKEN` / `RTOKEN` from before; `login` helper from Step 5)
**Profile**
```bash
curl http://localhost:5000/api/users/me -H "Authorization: Bearer $RTOKEN"
curl -X PUT http://localhost:5000/api/users/me -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"name": "Amit Kumar", "share_phone": true}'
curl -X PUT http://localhost:5000/api/users/me -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"flat_no": "E-505"}'
```
Expect `200`, `200`, then `400 reapproval_required` (nothing changed). Don't send `confirm_reapproval` unless you want to be locked out.

**Dues** (use Amit's real id, normally 2)
```bash
curl -X POST http://localhost:5000/api/dues -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"user_id": 2, "month": "2026-09", "amount": 2500, "due_date": "2026-09-10"}'
curl http://localhost:5000/api/dues/me -H "Authorization: Bearer $RTOKEN"
curl -X POST http://localhost:5000/api/dues/DUE_ID/remind -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"note": "September is overdue"}'
curl -X PATCH http://localhost:5000/api/dues/DUE_ID/mark-paid -H "Authorization: Bearer $STOKEN"
curl http://localhost:5000/api/notifications/me -H "Authorization: Bearer $RTOKEN"
```
The reminder is real Gemini text: check it is polite and uses only the amount/month given. The resident's
notifications should hold the reminder and then the payment receipt.

**Announcement management** (ids from `GET /api/announcements`)
```bash
curl -X PATCH http://localhost:5000/api/announcements/ID/pin -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"pinned": true}'
curl -X PATCH http://localhost:5000/api/announcements/ID -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"title": "Water tank cleaning - Friday"}'
```

**Amenity booking** (pick a date within 30 days; times are 24-hour)
```bash
curl -X POST http://localhost:5000/api/amenities -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"name": "Gym", "description": "Ground floor"}'
curl -X POST http://localhost:5000/api/amenity-bookings -H "Content-Type: application/json" -H "Authorization: Bearer $RTOKEN" -d '{"amenity_id": 1, "date": "2026-10-20", "start_time": "18:00", "end_time": "19:00"}'
curl -X POST http://localhost:5000/api/amenity-bookings -H "Content-Type: application/json" -H "Authorization: Bearer $STOKEN" -d '{"amenity_id": 1, "date": "2026-10-20", "start_time": "18:30", "end_time": "19:30"}'
curl "http://localhost:5000/api/amenities/1/availability?date=2026-10-20" -H "Authorization: Bearer $STOKEN"
curl -X DELETE http://localhost:5000/api/amenity-bookings/BOOKING_ID -H "Authorization: Bearer $STOKEN"
```
First booking `201`; the overlapping one `409 slot_taken` showing the existing 18:00-19:00 slot; the Secretary
cancelling Amit's booking works and Amit gets a notification.

**My Tickets**
```bash
curl http://localhost:5000/api/my-tickets -H "Authorization: Bearer $RTOKEN"
```

## Honest limits
- The double-booking **race** (two people booking the same slot at the same instant) is protected by a database row lock
  that only exists on PostgreSQL. My automated tests run on SQLite, so the lock itself is untested; the overlap logic is.
- A password change doesn't log out other devices: an old login token stays valid until it expires (7 days).
- Dues belong to one **account**. If two family members register for the same flat, `POST /api/dues` asks for `user_id`
  (it can't guess), and there is no "bill every flat" bulk action yet. Decide the rule (e.g. one billing account per flat)
  before building that.
- Still ahead: translate-on-read, Step 7 jobs (weekly chat cleanup, auto-escalation, duplicate detection), then the frontend.
