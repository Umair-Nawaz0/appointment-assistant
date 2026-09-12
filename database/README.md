# AI Appointment Assistant database

This directory contains the PostgreSQL data model for the multi-tenant AI
receptionist platform. The original 11 operational tables remain unchanged in
purpose. The business itself is the only dashboard authentication principal;
there is no users table. Two narrowly scoped support tables provide one-time
email codes and revocable sessions. It has no
billing, CRM, analytics, knowledge-base, audit-log, notes, tags, or
automation-log tables.

## Files

- `schema.sql` is the authoritative, complete, standalone production schema.
- `schema_snapshot.sql` is a schema-only `pg_dump` generated from a clean
  database after loading `schema.sql`.
- `enums.sql`, `constraints.sql`, and `indexes.sql` are focused copies of the
  matching definitions in `schema.sql` for review and maintenance. Do not run
  them after `schema.sql`, because the objects already exist.
- `seed.sql` inserts one small, internally consistent demo tenant.
- `erd/database_erd.pdf` is the single ERD artifact.

## Tables

| Area | Table | Purpose |
|---|---|---|
| Business | `businesses` | Tenant and login root with core profile, unique business email, password hash, verification state, status, and scheduling time zone. |
| Business | `business_settings` | One-to-one booking policy, daily capacity, and contact-collection settings. |
| Business | `business_hours` | One local opening interval per named weekday; a missing weekday is closed. |
| Business | `business_schedule_overrides` | Replaces weekly hours on one local date. A closed row models a holiday; a custom interval models a special opening, special closing, or half day. |
| Business | `business_channels` | One configuration row per business and supported channel. |
| Access | `business_auth_codes` | Hashed, expiring, single-use six-digit email-verification and password-reset codes, with an attempt limit. |
| Access | `business_sessions` | Hashed, expiring, revocable sessions for the authenticated business. |
| Customer | `customers` | Tenant-owned customer data only; it deliberately contains no contact identifiers. |
| Customer | `customer_identities` | Phone, email, Instagram user ID, website session, and other supported channel identities. |
| Conversation | `conversations` | One tenant/customer conversation on one configured channel, with an optional provider thread ID. |
| Conversation | `conversation_messages` | Unified incoming and outgoing message stream for every channel and media type. |
| Conversation | `conversation_state` | Exactly one current AI workflow state for each non-closed conversation. |
| Appointment | `appointments` | Scheduled appointment plus booking-time customer name, phone, and email snapshots. |

## Relationships and invariants

- A business owns its credentials, settings, hours, schedule overrides, channel
  configurations, customers, conversations, and appointments. Authentication
  codes and sessions cascade with the business.
- Dashboard login is intentionally one business email and password per tenant.
  Customers are not dashboard users; they connect only through normalized
  channel identities.
- A conversation channel must have a matching `business_channels` configuration
  row. Disabling that row preserves history; deleting it is blocked while a
  conversation still references it.
- `business_id` is deliberately repeated on identity, conversation, message,
  state, and appointment rows. Composite foreign keys ensure a child can never
  point to a customer or conversation from a different tenant.
- A customer can own many identities. The same identifier can exist at
  different businesses, while a tenant cannot assign the same channel identity
  to two customers. Email identity uniqueness is case-insensitive. Phone-like
  identifiers should be normalized to E.164 before insertion. An Instagram
  identity's `identifier` must be the Instagram User ID; the changeable username
  belongs in `display_name`.
- There can be at most one primary identity per customer and channel.
- A conversation owns many messages and has exactly one state row while it is
  non-closed, then none after it closes. Deferred checks let both rows be created
  in one transaction, and row locks serialize state changes against closing.
  Inserting a message advances
  `conversations.last_message_at` without moving the value backwards.
- An appointment's optional conversation must belong to the same business and
  customer. The snapshot contact columns never reference or auto-update from
  `customer_identities`, so later customer edits do not rewrite history.
- All tenant-owned rows cascade when a business is deliberately hard-deleted.
  Messages and state cascade with their conversation. Direct customer deletion
  is blocked while historical appointments exist, and a conversation referenced
  by an appointment cannot be removed by itself. The deferred foreign keys still
  allow an explicit whole-tenant deletion to complete atomically.
- Business hours and overrides are local to `businesses.timezone`. The database
  validates that the value is a PostgreSQL/IANA time-zone name. Appointment and
  message instants use `timestamptz`.

The exact minimal model supports one continuous opening interval per weekday
and per override date. Split shifts, staff/resources, per-service capacity, and
appointment overlap policies are intentionally outside this redesign. The
optional `maximum_appointments_per_day` setting provides a simple tenant-wide
daily booking cap without introducing services or resource tables.

## Enums

- `channel_type`: `WHATSAPP`, `PHONE`, `SMS`, `EMAIL`, `INSTAGRAM`, `WEBSITE`
- `business_status`: `ACTIVE`, `INACTIVE`, `SUSPENDED`
- `day_of_week`: `MONDAY`, `TUESDAY`, `WEDNESDAY`, `THURSDAY`, `FRIDAY`, `SATURDAY`, `SUNDAY`
- `conversation_status`: `ACTIVE`, `WAITING_CUSTOMER`, `WAITING_BUSINESS`, `CLOSED`
- `appointment_status`: `PENDING`, `CONFIRMED`, `CANCELLED`, `COMPLETED`, `NO_SHOW`
- `message_sender`: `CUSTOMER`, `AI`, `BUSINESS`, `SYSTEM`
- `message_type`: `TEXT`, `IMAGE`, `AUDIO`, `VIDEO`, `DOCUMENT`, `EMAIL`, `CALL_TRANSCRIPT`
- `business_auth_code_type`: `EMAIL_VERIFICATION`, `PASSWORD_RESET`

Provider names, AI intents, and workflow steps remain text because their values
are integration- or workflow-specific and can evolve without enum migrations.

## Live localhost database

PostgreSQL 13 or newer is required for the built-in `gen_random_uuid()` default.
The deployed database is named exactly `apointment_assitant` and is owned by the
local PostgreSQL role `umair`. It is separate from the existing `project` and
`nextora` databases; those databases are outside this schema's scope.

To reproduce the deployment from the project root:

```bash
sudo -u postgres createdb --owner=umair apointment_assitant
psql -X --set=ON_ERROR_STOP=1 --dbname=apointment_assitant \
  --file=database/schema.sql
```

`schema.sql` intentionally does not drop existing objects and must be loaded
into a new, empty database. It must not be run over `project` or another
existing application database.

For the current localhost deployment, `migrations/002_business_direct_auth.sql`
removes the earlier user-account layer, moves the login fields to `businesses`,
and creates only the two direct-business authentication support tables. It does
not change the 11 operational table relationships.

## Load demo data

The seed is optional and should be used only in development or testing:

```bash
psql -X --set=ON_ERROR_STOP=1 --dbname=apointment_assitant \
  --file=database/seed.sql
```

It creates one verified demo business, settings, weekday hours, one holiday override, one
website channel, one customer with website and email identities, one active
conversation with state and a message, and one pending appointment. The demo
password value is deliberately not a usable application password hash. The seed
has not been loaded into the live localhost database.

## Regenerate the schema snapshot

After loading `schema.sql` into a clean database, regenerate the snapshot with:

```bash
pg_dump --schema-only --no-owner --no-privileges \
  --schema=public --dbname=apointment_assitant \
  --file=database/schema_snapshot.sql
```

The snapshot is generated output. Make design changes in `schema.sql`, then
reload a clean database and regenerate the snapshot rather than editing it by
hand.
