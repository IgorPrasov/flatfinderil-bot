-- FlatFinder IL — PostgreSQL schema
-- Run once to initialize the database

CREATE TABLE IF NOT EXISTS listings (
    id          SERIAL PRIMARY KEY,
    title       TEXT,
    description TEXT,
    property_type VARCHAR(50),
    city        VARCHAR(100),
    district    VARCHAR(100),
    neighborhood VARCHAR(100),
    rooms       VARCHAR(20),
    floor       INTEGER,
    floors_total INTEGER,
    area_sqm    FLOAT DEFAULT 0,
    price       INTEGER DEFAULT 0,
    deal_type   VARCHAR(20),
    parking     INTEGER DEFAULT 0,
    pool        BOOLEAN DEFAULT FALSE,
    infrastructure JSONB DEFAULT '[]',
    contact     TEXT,
    photos      JSONB DEFAULT '[]',
    source      VARCHAR(50),
    source_url  TEXT,
    date_added  DATE DEFAULT CURRENT_DATE,
    active      BOOLEAN DEFAULT TRUE,
    views       INTEGER DEFAULT 0,
    view_requests INTEGER DEFAULT 0,
    poster_type VARCHAR(20),
    poster_name TEXT,
    poster_phone TEXT,
    poster_username TEXT,
    lat         FLOAT,
    lng         FLOAT,
    ai_score    INTEGER,
    is_duplicate BOOLEAN DEFAULT FALSE,
    is_suspicious BOOLEAN DEFAULT FALSE,
    suspicion_reason TEXT,
    seller_type VARCHAR(20),
    user_id     BIGINT,
    deal_closed BOOLEAN DEFAULT FALSE,
    deal_id     INTEGER,
    extra       JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_listings_city ON listings(city);
CREATE INDEX IF NOT EXISTS idx_listings_deal_type ON listings(deal_type);
CREATE INDEX IF NOT EXISTS idx_listings_active ON listings(active);
CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);
CREATE INDEX IF NOT EXISTS idx_listings_source_url ON listings(source_url) WHERE source_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_listings_user_id ON listings(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_listings_date_added ON listings(date_added);

CREATE TABLE IF NOT EXISTS favorites (
    user_id    BIGINT,
    listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,
    price_at_save INTEGER,
    PRIMARY KEY (user_id, listing_id)
);

CREATE TABLE IF NOT EXISTS user_listings (
    user_id    BIGINT,
    listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, listing_id)
);

CREATE TABLE IF NOT EXISTS paid_subscriptions (
    user_id    BIGINT,
    plan_type  VARCHAR(50),
    expiry_iso TIMESTAMPTZ,
    PRIMARY KEY (user_id, plan_type)
);

CREATE TABLE IF NOT EXISTS search_subscriptions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      BIGINT NOT NULL,
    filters      JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    last_checked TIMESTAMPTZ,
    last_result_ids JSONB DEFAULT '[]',
    is_alert     BOOLEAN DEFAULT FALSE,
    alert_expiry TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_search_subs_user ON search_subscriptions(user_id);

CREATE TABLE IF NOT EXISTS reviews (
    id         SERIAL PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id) ON DELETE CASCADE,
    user_id    BIGINT,
    rating     INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (listing_id, user_id)
);

CREATE TABLE IF NOT EXISTS referrals (
    referrer_id BIGINT,
    new_user_id BIGINT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (referrer_id, new_user_id)
);

CREATE TABLE IF NOT EXISTS user_meta (
    user_id            BIGINT PRIMARY KEY,
    bonus_expiry       TIMESTAMPTZ,
    free_listing_used  BOOLEAN DEFAULT FALSE,
    trial_warning      JSONB DEFAULT '{}',
    listing_credits    JSONB DEFAULT '{"count": 0, "expiry": null}',
    service_sub_expiry TIMESTAMPTZ,
    alert_expiry       TIMESTAMPTZ,
    lead_balance       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS listing_fingerprints (
    fingerprint TEXT PRIMARY KEY,
    listing_id  INTEGER
);

CREATE TABLE IF NOT EXISTS services (
    id               SERIAL PRIMARY KEY,
    service_type     VARCHAR(50),
    name             TEXT,
    phone            TEXT,
    city             VARCHAR(100),
    region           VARCHAR(100),
    description      TEXT,
    price            INTEGER,
    subscription_ils INTEGER,
    active           BOOLEAN DEFAULT TRUE,
    views            INTEGER DEFAULT 0,
    user_id          BIGINT,
    date_added       DATE DEFAULT CURRENT_DATE,
    extra            JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS service_subscriptions (
    service_id  VARCHAR(50) PRIMARY KEY,
    plan_key    VARCHAR(50),
    expiry      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS phone_data (
    phone        VARCHAR(30) PRIMARY KEY,
    is_agent     BOOLEAN DEFAULT FALSE,
    post_count   INTEGER DEFAULT 0,
    blacklisted  BOOLEAN DEFAULT FALSE,
    reports      JSONB DEFAULT '[]',
    data         JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS crm_contacts (
    id           SERIAL PRIMARY KEY,
    user_id      BIGINT,
    name         TEXT,
    phone        TEXT,
    notes        TEXT,
    contact_type VARCHAR(50),
    region       VARCHAR(100),
    city         VARCHAR(100),
    active       BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    extra        JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT,
    contact_id INTEGER REFERENCES crm_contacts(id),
    listing_id INTEGER,
    status     VARCHAR(50),
    notes      TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    extra      JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS crm_notes (
    id         SERIAL PRIMARY KEY,
    contact_id INTEGER REFERENCES crm_contacts(id) ON DELETE CASCADE,
    text       TEXT,
    author_id  BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS closed_deals (
    id             SERIAL PRIMARY KEY,
    listing_id     INTEGER,
    owner_id       BIGINT,
    tenant_id      BIGINT,
    listed_price   INTEGER,
    deal_price     INTEGER,
    deal_type      VARCHAR(20),
    property_type  VARCHAR(50),
    city           VARCHAR(100),
    rooms          VARCHAR(20),
    days_to_close  INTEGER,
    closed_at      DATE,
    confirmed_by   VARCHAR(20),
    tenant_confirmed BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS view_requesters (
    listing_id INTEGER,
    user_id    BIGINT,
    username   TEXT,
    name       TEXT,
    date_added DATE DEFAULT CURRENT_DATE,
    PRIMARY KEY (listing_id, user_id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS support_messages (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT,
    username   TEXT,
    first_name TEXT,
    lang       VARCHAR(10),
    text       TEXT,
    date       TIMESTAMPTZ DEFAULT NOW(),
    read       BOOLEAN DEFAULT FALSE,
    reply      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS client_leads (
    id         VARCHAR(20) PRIMARY KEY,
    type       VARCHAR(50),
    city       VARCHAR(100),
    status     VARCHAR(20) DEFAULT 'open',
    buyers     JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    extra      JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS unlocked_leads (
    user_id BIGINT,
    lead_id VARCHAR(20),
    PRIMARY KEY (user_id, lead_id)
);

CREATE TABLE IF NOT EXISTS pending_lead_triggers (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT,
    type        VARCHAR(50),
    city        VARCHAR(100),
    send_after  TIMESTAMPTZ,
    sent        BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    user_id    BIGINT PRIMARY KEY,
    email      TEXT,
    lang       VARCHAR(10) DEFAULT 'ru',
    owner_name TEXT,
    owner_phone TEXT,
    extra      JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS service_profiles (
    user_id BIGINT PRIMARY KEY,
    email   TEXT,
    extra   JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS bot_users (
    user_id    BIGINT PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    last_name  TEXT,
    lang       VARCHAR(10) DEFAULT 'ru',
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bot_users_last_seen ON bot_users(last_seen);
