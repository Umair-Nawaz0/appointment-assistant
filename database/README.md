# AI Appointment Assistant database

This directory contains the PostgreSQL data model for the multi-tenant AI
appointment assistant platform. The architecture is designed as a single, website-first
AI appointment assistant where customers can chat naturally without requiring upfront
registration. When a customer enters the appointment booking flow, their required
contact details are collected, a customer profile is created and linked to the conversation,
and the appointment is scheduled after availability verification and confirmation.

The platform consists of 11 operational tables. The business itself is the only dashboard
authentication principal; there is no separate users table. Two narrowly scoped support tables
provide one-time email codes and revocable sessions.

## Files

- `schema.sql` is the authoritative, complete, standalone production schema.
- `schema_snapshot.sql` is a schema-only `pg_dump` generated from a clean
  database after loading `schema.sql`.
- `enums.sql`, `constraints.sql`, and `indexes.sql` are focused copies of the
  matching definitions in `schema.sql` for review and maintenance. Do not run
  them after `schema.sql`, because the objects already exist.
- `seed.sql` inserts one small, internally consistent demo tenant.
- `erd/database_erd.pdf` is the single ERD artifact.

## Tables (11 Operational Tables)

| Area | Table | Purpose |
|---|---|---|
| Business | `businesses` | Tenant and login root with core profile, unique business email, password hash, verification state, status, and scheduling time zone. |
| Business | `business_settings` | One-to-one booking policy, daily capacity, and contact-collection settings. |
| Business | `business_hours` | One local opening interval per named weekday; a missing weekday is closed. |
| Business | `business_schedule_overrides` | Replaces weekly hours on one local date. A closed row models a holiday; a custom interval models a special opening, special closing, or half day. |
| Access | `business_auth_codes` | Hashed, expiring, single-use six-digit email-verification and password-reset codes, with an attempt limit. |
| Access | `business_sessions` | Hashed, expiring, revocable sessions for the authenticated business. |
| Customer | `customers` | Tenant-owned customer profile (name, phone, email) created upon entering the booking flow. |
| Conversation | `conversations` | Natural chat stream between an anonymous visitor or customer and the AI assistant; `customer_id` is nullable. |
| Conversation | `conversation_messages` | Unified incoming and outgoing message stream (text, image, audio, video, document). |
| Conversation | `conversation_state` | Exactly one current AI workflow state for each non-closed conversation. |
| Appointment | `appointments` | Scheduled appointment plus booking-time customer name, phone, and email snapshots. |

## Relationships and Invariants

- A business owns its credentials, settings, hours, schedule overrides, customers,
  conversations, and appointments. Authentication codes and sessions cascade with the business.
- Dashboard login is intentionally one business email and password per tenant.
- Anonymous visitors can chat naturally with the AI assistant. `conversations.customer_id`
  is nullable. When the visitor initiates an appointment booking flow, their contact details
  (`name`, `phone`, `email`) are collected, a `customers` row is created, and the conversation is
  associated with the new customer record.
- `business_id` is repeated on conversation, message, state, customer, and appointment rows.
  Composite foreign keys ensure child entities cannot point to records from a different tenant.
- A conversation owns many messages and has exactly one state row while it is
  non-closed, then none after it closes. Deferred checks let both rows be created
  in one transaction, and row locks serialize state changes against closing.
  Inserting a message advances `conversations.last_message_at` monotonically.
- An appointment references both the customer and optionally the conversation.
  When linked, the composite foreign key `(business_id, customer_id, conversation_id)` guarantees
  that the appointment, customer, and conversation all belong to the exact same tenant and customer.
- Appointments store snapshot contact columns (`customer_name`, `customer_phone`, `customer_email`)
  at booking confirmation time so future profile modifications do not rewrite historical booking data.
- All tenant-owned rows cascade when a business is hard-deleted.
  Messages and state cascade with their conversation. Direct customer deletion sets
  `conversations.customer_id` to NULL (preserving chat history), while customer deletion is blocked
  if historical appointments exist.
- Business hours and overrides are local to `businesses.timezone`. The database
  validates that the value is a PostgreSQL/IANA time-zone name. Appointment and
  message instants use `timestamptz`.

The exact minimal model supports one continuous opening interval per weekday
and per override date. Split shifts, staff/resources, per-service capacity, and
appointment overlap policies are intentionally outside this model. The
optional `maximum_appointments_per_day` setting provides a simple tenant-wide
daily booking cap.

## Enums

- `business_status`: `ACTIVE`, `INACTIVE`, `SUSPENDED`
- `day_of_week`: `MONDAY`, `TUESDAY`, `WEDNESDAY`, `THURSDAY`, `FRIDAY`, `SATURDAY`, `SUNDAY`
- `conversation_status`: `ACTIVE`, `WAITING_CUSTOMER`, `WAITING_BUSINESS`, `CLOSED`
- `appointment_status`: `PENDING`, `CONFIRMED`, `CANCELLED`, `COMPLETED`, `NO_SHOW`
- `message_sender`: `CUSTOMER`, `AI`, `BUSINESS`, `SYSTEM`
- `message_type`: `TEXT`, `IMAGE`, `AUDIO`, `VIDEO`, `DOCUMENT`
- `business_auth_code_type`: `EMAIL_VERIFICATION`, `PASSWORD_RESET`

## Live Localhost Database

PostgreSQL 13 or newer is required for the built-in `gen_random_uuid()` default (PostgreSQL 15+ for `ON DELETE SET NULL (column)`).
The deployed database is named `apointment_assitant` and is owned by the local PostgreSQL role `umair`.

To reproduce the deployment from the project root:

```bash
psql -X --set=ON_ERROR_STOP=1 --dbname=apointment_assitant \
  --file=database/schema.sql
```

## Load Demo Data

The seed is optional and should be used only in development or testing:

```bash
psql -X --set=ON_ERROR_STOP=1 --dbname=apointment_assitant \
  --file=database/seed.sql
```

## Regenerate the Schema Snapshot

After loading `schema.sql` into a clean database, regenerate the snapshot with:

```bash
pg_dump --schema-only --no-owner --no-privileges \
  --schema=public --dbname=apointment_assitant \
  --file=database/schema_snapshot.sql
```
