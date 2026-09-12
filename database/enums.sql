CREATE TYPE channel_type AS ENUM (
    'WHATSAPP',
    'PHONE',
    'SMS',
    'EMAIL',
    'INSTAGRAM',
    'WEBSITE'
);

CREATE TYPE business_status AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'SUSPENDED'
);

CREATE TYPE day_of_week AS ENUM (
    'MONDAY',
    'TUESDAY',
    'WEDNESDAY',
    'THURSDAY',
    'FRIDAY',
    'SATURDAY',
    'SUNDAY'
);

CREATE TYPE business_auth_code_type AS ENUM (
    'EMAIL_VERIFICATION',
    'PASSWORD_RESET'
);

CREATE TYPE conversation_status AS ENUM (
    'ACTIVE',
    'WAITING_CUSTOMER',
    'WAITING_BUSINESS',
    'CLOSED'
);

CREATE TYPE appointment_status AS ENUM (
    'PENDING',
    'CONFIRMED',
    'CANCELLED',
    'COMPLETED',
    'NO_SHOW'
);

CREATE TYPE message_sender AS ENUM (
    'CUSTOMER',
    'AI',
    'BUSINESS',
    'SYSTEM'
);

CREATE TYPE message_type AS ENUM (
    'TEXT',
    'IMAGE',
    'AUDIO',
    'VIDEO',
    'DOCUMENT',
    'EMAIL',
    'CALL_TRANSCRIPT'
);
