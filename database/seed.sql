BEGIN;

INSERT INTO businesses (
    id,
    name,
    email,
    password_hash,
    address,
    city,
    state_province,
    postal_code,
    country_code,
    industry,
    timezone,
    status,
    email_verified_at
)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    'Demo Wellness Studio',
    'owner@example.com',
    'seed-only-password-hash-not-for-authentication',
    '42 Wellness Avenue',
    'Karachi',
    'Sindh',
    '74000',
    'PK',
    'Wellness',
    'Asia/Karachi',
    'ACTIVE',
    TIMESTAMPTZ '2030-01-01 00:00:00+00'
);

INSERT INTO business_settings (
    business_id,
    appointment_duration_minutes,
    booking_window_days,
    maximum_appointments_per_day,
    allow_cancellation,
    allow_reschedule,
    collect_phone,
    collect_email,
    confirmation_required
)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    30,
    60,
    20,
    true,
    true,
    true,
    true,
    true
);

INSERT INTO business_hours (business_id, day_of_week, opens_at, closes_at)
VALUES
    ('00000000-0000-4000-8000-000000000001', 'MONDAY', '09:00', '17:00'),
    ('00000000-0000-4000-8000-000000000001', 'TUESDAY', '09:00', '17:00'),
    ('00000000-0000-4000-8000-000000000001', 'WEDNESDAY', '09:00', '17:00'),
    ('00000000-0000-4000-8000-000000000001', 'THURSDAY', '09:00', '17:00'),
    ('00000000-0000-4000-8000-000000000001', 'FRIDAY', '09:00', '17:00');

INSERT INTO business_schedule_overrides (
    business_id,
    override_date,
    is_closed,
    reason
)
VALUES (
    '00000000-0000-4000-8000-000000000001',
    DATE '2030-01-01',
    true,
    'New Year holiday'
);

INSERT INTO customers (
    id,
    business_id,
    name,
    phone,
    email
)
VALUES (
    '00000000-0000-4000-8000-000000000002',
    '00000000-0000-4000-8000-000000000001',
    'Demo Customer',
    '+923001234567',
    'demo.customer@example.com'
);

INSERT INTO conversations (
    id,
    business_id,
    customer_id,
    external_conversation_id,
    status,
    started_at
)
VALUES (
    '00000000-0000-4000-8000-000000000005',
    '00000000-0000-4000-8000-000000000001',
    '00000000-0000-4000-8000-000000000002',
    'demo-website-thread-001',
    'ACTIVE',
    TIMESTAMPTZ '2030-01-10 09:00:00+05'
);

INSERT INTO conversation_messages (
    id,
    business_id,
    conversation_id,
    sender,
    message_type,
    content,
    external_message_id,
    metadata,
    sent_at
)
VALUES (
    '00000000-0000-4000-8000-000000000006',
    '00000000-0000-4000-8000-000000000001',
    '00000000-0000-4000-8000-000000000005',
    'CUSTOMER',
    'TEXT',
    'I would like to book an appointment.',
    'demo-message-001',
    '{"source":"website_widget"}'::jsonb,
    TIMESTAMPTZ '2030-01-10 09:01:00+05'
);

INSERT INTO conversation_state (
    conversation_id,
    business_id,
    current_intent,
    current_step,
    collected_data,
    context_summary,
    last_ai_response
)
VALUES (
    '00000000-0000-4000-8000-000000000005',
    '00000000-0000-4000-8000-000000000001',
    'BOOK_APPOINTMENT',
    'CONFIRM_DETAILS',
    '{"customer_email":"demo.customer@example.com","customer_phone":"+923001234567"}'::jsonb,
    'Customer selected an available morning appointment.',
    'Please confirm your appointment details.'
);

INSERT INTO appointments (
    id,
    business_id,
    customer_id,
    conversation_id,
    status,
    scheduled_start,
    scheduled_end,
    customer_name,
    customer_phone,
    customer_email
)
VALUES (
    '00000000-0000-4000-8000-000000000007',
    '00000000-0000-4000-8000-000000000001',
    '00000000-0000-4000-8000-000000000002',
    '00000000-0000-4000-8000-000000000005',
    'PENDING',
    TIMESTAMPTZ '2030-01-15 10:00:00+05',
    TIMESTAMPTZ '2030-01-15 10:30:00+05',
    'Demo Customer',
    '+923001234567',
    'demo.customer@example.com'
);

COMMIT;
