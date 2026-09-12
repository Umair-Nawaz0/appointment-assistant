BEGIN;

SET LOCAL client_min_messages = warning;
SET LOCAL search_path = public, pg_catalog;

-- The business is the dashboard authentication principal. Preserve the
-- preferred existing account per business while removing the user layer.
ALTER TABLE businesses
    ADD COLUMN email text,
    ADD COLUMN password_hash text,
    ADD COLUMN email_verified_at timestamp with time zone,
    ADD COLUMN last_login_at timestamp with time zone;

WITH preferred_account AS (
    SELECT DISTINCT ON (business_id)
           business_id,
           email,
           password_hash,
           email_verified_at,
           last_login_at
      FROM users
     ORDER BY business_id,
              CASE role WHEN 'OWNER'::user_role THEN 1 WHEN 'ADMIN'::user_role THEN 2 ELSE 3 END,
              created_at,
              id
)
UPDATE businesses AS business
   SET email = account.email,
       password_hash = account.password_hash,
       email_verified_at = account.email_verified_at,
       last_login_at = account.last_login_at
  FROM preferred_account AS account
 WHERE account.business_id = business.id;

DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1 FROM businesses WHERE email IS NULL OR password_hash IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot migrate: every existing business must have a dashboard account';
    END IF;
END;
$migration$;

DROP TABLE auth_tokens;
DROP TABLE user_sessions;
DROP TABLE users;
DROP TYPE auth_token_type;
DROP TYPE user_status;
DROP TYPE user_role;

ALTER TABLE businesses
    ALTER COLUMN email SET NOT NULL,
    ALTER COLUMN password_hash SET NOT NULL,
    ADD CONSTRAINT uq_businesses_email UNIQUE (email),
    ADD CONSTRAINT ck_businesses_email CHECK (
        email = lower(btrim(email))
        AND email LIKE '%_@_%._%'
        AND email !~ '[[:space:]]'::text
    ),
    ADD CONSTRAINT ck_businesses_password_hash CHECK (length(password_hash) >= 32),
    ADD CONSTRAINT ck_businesses_verified_time CHECK (
        email_verified_at IS NULL OR email_verified_at >= created_at
    ),
    ADD CONSTRAINT ck_businesses_last_login_time CHECK (
        last_login_at IS NULL OR last_login_at >= created_at
    );

CREATE TYPE business_auth_code_type AS ENUM (
    'EMAIL_VERIFICATION',
    'PASSWORD_RESET'
);

CREATE TABLE business_auth_codes (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    code_type business_auth_code_type NOT NULL,
    code_hash character(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    consumed_at timestamp with time zone,
    attempt_count smallint DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_business_auth_codes PRIMARY KEY (id),
    CONSTRAINT uq_business_auth_codes_hash UNIQUE (code_hash),
    CONSTRAINT ck_business_auth_codes_hash CHECK (code_hash ~ '^[0-9a-f]{64}$'::text),
    CONSTRAINT ck_business_auth_codes_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_business_auth_codes_consumed_time CHECK (
        consumed_at IS NULL OR consumed_at >= created_at
    ),
    CONSTRAINT ck_business_auth_codes_attempts CHECK (attempt_count BETWEEN 0 AND 5),
    CONSTRAINT fk_business_auth_codes_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE
);

CREATE TABLE business_sessions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    business_id uuid NOT NULL,
    token_hash character(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    last_seen_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    revoked_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT pk_business_sessions PRIMARY KEY (id),
    CONSTRAINT uq_business_sessions_hash UNIQUE (token_hash),
    CONSTRAINT ck_business_sessions_hash CHECK (token_hash ~ '^[0-9a-f]{64}$'::text),
    CONSTRAINT ck_business_sessions_expiry CHECK (expires_at > created_at),
    CONSTRAINT ck_business_sessions_last_seen CHECK (last_seen_at >= created_at),
    CONSTRAINT ck_business_sessions_revoked_time CHECK (
        revoked_at IS NULL OR revoked_at >= created_at
    ),
    CONSTRAINT fk_business_sessions_business FOREIGN KEY (business_id)
        REFERENCES businesses(id) ON UPDATE NO ACTION ON DELETE CASCADE
);

CREATE INDEX idx_business_auth_codes_active
    ON business_auth_codes USING btree (business_id, code_type, expires_at DESC)
    WHERE consumed_at IS NULL;

CREATE INDEX idx_business_sessions_active
    ON business_sessions USING btree (business_id, expires_at DESC)
    WHERE revoked_at IS NULL;

COMMENT ON COLUMN businesses.email IS
    'Unique dashboard login and verification email for the business itself.';
COMMENT ON COLUMN businesses.password_hash IS
    'Strong one-way password hash for direct business authentication.';
COMMENT ON TABLE business_auth_codes IS
    'Short-lived hashed codes for business email verification and password reset.';
COMMENT ON TABLE business_sessions IS
    'Revocable sessions for authenticated businesses, identified by hashed cookie tokens.';

COMMIT;
