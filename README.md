# GrievDesk frontend (steps 1 and 2)

React + Vite (JavaScript), Tailwind + shadcn-style components, React Router, TanStack Query, react-i18next.
It talks to the Flask backend in `grievdesk-backend`.

## Run it

1. Start your backend (`python run.py`, port 5000).
2. In this folder:

       npm install
       cp .env.example .env      # on Windows: copy .env.example .env
       npm run dev

3. Open http://localhost:5173

Edit `.env` to set `VITE_API_URL` if your backend is not on http://localhost:5000, and `VITE_SOCIETY_NAME`
for the header. Restart `npm run dev` after changing `.env`.

## What works now

- Landing page, login, register (resident or Secretary), pending-approval message
- Token handling: the JWT is stored in localStorage and sent as `Authorization: Bearer ...`
- Any 401 from the API logs the user out and shows "Your session expired"
- Role-aware app shell: sidebar, mobile drawer, search and notification buttons, profile and log out
- Routes for every later screen, each showing a "built in step N" placeholder
- UI language follows the user's saved preference (English strings only for now)

## First-time test flow

1. Register as the Secretary (tick the Secretary box). It is approved automatically. Log in.
2. Register a resident in another browser or a private window. Logging in shows "awaiting approval".
3. Approve the resident. The approval screen is built in step 11, so until then call the API once.
   Get your Secretary token from the browser (DevTools > Application > Local Storage > grievdesk_token),
   find the resident's id in the register response or the database, then:

       curl -X PATCH http://localhost:5000/api/users/2/approve -H "Authorization: Bearer YOUR_TOKEN"

4. Log in as the resident.

## Folder guide

    src/lib/api.js        every backend call goes through here (token, error handling)
    src/lib/auth.jsx      login, register, logout, current user and role
    src/lib/local.js      local(item, 'field') picks the translated "<field>_local" text
    src/lib/constants.js  statuses, categories, roles. They match the backend exactly
    src/locales/en.json   all UI text (hi.json and or.json come in the translations step)
    src/components/       AppShell (sidebar), route guards, UI components
    src/pages/            Landing, Login, Register, ComingSoon (placeholder)

## Next steps

Step 3 is the chat screen: type picker, messages, Recents.
