# Appointment Assistant dashboard

A production-oriented, multi-tenant dashboard and API for the PostgreSQL AI
appointment assistant schema. The application is intentionally split into:

- `frontend/` — React, TypeScript, Vite, and responsive dashboard UI.
- `backend/` — FastAPI, Python, async PostgreSQL, secure authentication, and APIs.
- `database/` — authoritative SQL, focused schema files, migration, seed, and ERD.

## Included workflows

- Business sign-up, email verification, login, logout, forgot password, and
  one-time password reset.
- Dashboard overview, business profile, booking settings, weekly hours,
  schedule overrides, and channel configuration.
- Tenant-scoped customers and channel identities, appointments,
  conversations, message replies, and AI conversation state.
- HttpOnly server-side business sessions, scrypt password hashes, hashed
  six-digit codes, validation, attempt limits, rate limits, security headers,
  and trusted-origin checks.

## Run locally

PostgreSQL database `apointment_assitant` is already configured in `.env` for
local peer authentication. The Python environment has already been created.
Start the frontend and backend together:

```bash
npm run dev
```

Open <http://localhost:5173>. The API runs on <http://127.0.0.1:4000> and Vite
proxies `/api` requests to it.

Local development trusts both `http://localhost:5173` and
`http://127.0.0.1:5173`. For additional deployed frontend domains, provide a
comma-separated `FRONTEND_ORIGINS` value; unlisted origins remain blocked.

Development email delivery can use `MAIL_MODE=console`, where verification and
reset codes are printed by the backend and returned to the local UI. For real
email delivery, set `MAIL_MODE=smtp` and the `SMTP_*` values shown in
`.env.example`.

To run only the backend with Uvicorn:

```bash
backend/.venv/bin/uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 4000
```

FastAPI documentation is available at <http://127.0.0.1:4000/docs>.

## Production

```bash
npm run typecheck
npm run build
backend/.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 4000
```

FastAPI serves the compiled `frontend/dist` when it exists. Set a real `APP_URL`,
`FRONTEND_ORIGIN`, SMTP configuration, and database credentials in the runtime
environment. Put the process behind HTTPS so the secure session cookie is used.

## API surface

All responses are JSON. Auth uses the `appointment_session` HttpOnly cookie.

| Area | Routes |
|---|---|
| Auth | `/api/auth/signup`, `/verify-email`, `/resend-verification`, `/login`, `/forgot-password`, `/reset-password`, `/me`, `/logout` |
| Dashboard | `/api/dashboard/summary` |
| Business | `/api/business`, `/settings`, `/hours`, `/overrides/:date`, `/channels/:channel` |
| Customers | `/api/customers`, `/customers/:id`, `/customers/:id/identities` |
| Appointments | `/api/appointments`, `/appointments/:id` |
| Conversations | `/api/conversations`, `/conversations/:id`, `/status`, `/state`, `/messages` |

The backend derives `business_id` from the authenticated session. Clients
cannot supply a tenant ID, which prevents cross-business access through the API.

## Verification

`npm run typecheck`, `npm run build`, and `backend/.venv/bin/pytest -q backend/tests`
cover the main quality gates. The integration test exercises authentication,
business configuration, hours, overrides, channels, customers, identities,
appointments, conversations, AI state, messages, dashboard metrics, and logout
against an isolated PostgreSQL database.
