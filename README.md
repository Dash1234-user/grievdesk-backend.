# GrievDesk Backend — Step 1: Foundation (Auth + Users)

This is the first build milestone from the project brief: Flask skeleton, PostgreSQL
connection, the `users` table, and working registration/login with JWT — enforcing
the Secretary-uniqueness rule and the pending-approval flow for residents.
No frontend yet — test everything with `curl`.

## 1. Setup on Ubuntu

```bash
# From inside the grievdesk-backend folder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Create the PostgreSQL database

```bash
sudo -u postgres psql
```
Then inside the `psql` prompt:
```sql
CREATE USER grievdesk_user WITH PASSWORD 'changeme';
CREATE DATABASE grievdesk OWNER grievdesk_user;
\q
```

## 3. Configure environment

```bash
cp .env.example .env
```
Edit `.env` and make sure `DATABASE_URL` matches the user/password/db name you just
created, and set a real `JWT_SECRET_KEY` (the file shows how to generate one).

## 4. Run the database migration

```bash
flask db init        # only the very first time
flask db migrate -m "create users table"
flask db upgrade
```

This creates the `users` table, including the partial unique index that enforces
"only one Secretary at a time" at the database level.

## 5. Start the server

```bash
python run.py
```

It should start on `http://localhost:5000`. Confirm it's alive:
```bash
curl http://localhost:5000/api/health
# {"status":"ok"}
```

## 6. Test the registration + login flow

**Register the Secretary (first admin account):**
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "role": "admin",
    "name": "Rajesh Sharma",
    "phone": "9000000000",
    "flat_no": "A-101",
    "block_no": "A",
    "gmail": "secretary@example.com",
    "preferred_language": "en",
    "password": "SecurePass123"
  }'
```
Expect `201` with `"role": "secretary"` in the response.

**Try registering a second admin (should fail):**
Run the same request again with a different gmail but `"role": "admin"` —
expect `409 {"error": "secretary_already_exists"}`.

**Register a resident:**
```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "role": "resident",
    "name": "Amit",
    "phone": "9111111111",
    "flat_no": "B-204",
    "block_no": "B",
    "gmail": "resident1@example.com",
    "preferred_language": "or",
    "password": "ResidentPass123"
  }'
```
Expect `201` with `"approval_status": "pending"`.

**Try logging in as that resident before approval (should fail):**
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"gmail": "resident1@example.com", "password": "ResidentPass123"}'
```
Expect `403 {"error": "pending_approval"}` — this confirms Edge Case 9 from the
design doc is actually enforced, not just described.

**Log in as the Secretary (works immediately, no approval needed):**
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"gmail": "secretary@example.com", "password": "SecurePass123"}'
```
Expect `200` with an `access_token` — save this, you'll need it for the
approve-resident endpoint once it's built in a later step.

## What's intentionally NOT built yet

Approving the pending resident (`PATCH /api/users/<id>/approve`), and every other
endpoint from the design doc's Section 9, come in the next steps — this milestone
is deliberately just the foundation: schema + auth + the two uniqueness/approval
rules, fully tested before anything else gets layered on top.

## Project structure

```
grievdesk-backend/
├── app/
│   ├── __init__.py        # app factory
│   ├── config.py          # env-based config
│   ├── extensions.py      # db, migrate, jwt, cors instances
│   ├── models/
│   │   └── user.py        # User model + Role/ApprovalStatus constants
│   ├── routes/
│   │   └── auth.py        # /api/auth/register, /api/auth/login
│   └── utils/
│       └── decorators.py  # login_required, committee_or_secretary_required,
│                           # secretary_required — ready for the next steps
├── run.py
├── requirements.txt
├── .env.example
└── README.md
```
