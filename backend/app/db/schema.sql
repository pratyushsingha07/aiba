-- ============================================================================
-- Phase 2 Supabase Schema
-- Run this in Supabase Dashboard → SQL Editor, or via psql with DATABASE_URL.
--
-- Prerequisites:
--   • Supabase project created with Auth enabled
--   • Run as the postgres superuser (service role) — not as anon
-- ============================================================================

-- Enable pgcrypto for gen_random_uuid() if not already enabled
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- 1. organizations
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizations (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text        NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- 2. users  (mirrors/extends auth.users)
-- ---------------------------------------------------------------------------
CREATE TYPE IF NOT EXISTS user_role AS ENUM (
    'admin',
    'business_head',
    'category_manager',
    'analyst'
);

CREATE TABLE IF NOT EXISTS users (
    id                  uuid        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    org_id              uuid        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email               text        NOT NULL,
    role                user_role   NOT NULL DEFAULT 'analyst',
    -- NULL means the user can see all categories.
    -- Non-NULL is only meaningful for role = 'category_manager'.
    assigned_category   text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users may only see/update their own org's rows
CREATE POLICY "users_org_isolation" ON users
    USING  (org_id = (auth.jwt() ->> 'org_id')::uuid)
    WITH CHECK (org_id = (auth.jwt() ->> 'org_id')::uuid);

-- ---------------------------------------------------------------------------
-- 3. datasets
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS datasets (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by     uuid        NOT NULL REFERENCES users(id),
    filename        text        NOT NULL,
    -- Supabase Storage path, e.g. "{org_id}/{dataset_id}/filename.xlsx"
    -- NULL while status = 'pending' (file hasn't been confirmed yet)
    storage_path    text,
    uploaded_at     timestamptz NOT NULL DEFAULT now(),
    -- 'pending' → file uploaded but not confirmed
    -- 'active'  → confirmed, KPIs computed, permanently stored
    -- 'failed'  → confirm step failed with a blocking validation error
    status          text        NOT NULL DEFAULT 'pending'
);

ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "datasets_org_isolation" ON datasets
    USING  (org_id = (auth.jwt() ->> 'org_id')::uuid)
    WITH CHECK (org_id = (auth.jwt() ->> 'org_id')::uuid);

-- ---------------------------------------------------------------------------
-- 4. kpi_snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id              uuid        NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    kpi_json                jsonb       NOT NULL,
    -- Records which margin values were used per category at calculation time,
    -- including whether each margin was a confirmed figure or a default estimate.
    category_margins_used   jsonb,
    created_at              timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE kpi_snapshots ENABLE ROW LEVEL SECURITY;

-- kpi_snapshots has no org_id column; org isolation is enforced via the parent datasets row.
-- NOTE: Postgres RLS cannot filter *inside* the kpi_json JSONB blob. Category-level
--       access restriction for 'category_manager' users is enforced at the application
--       layer in GET /dashboard/{dataset_id}. See app/api/dashboard.py for details.
CREATE POLICY "kpi_snapshots_org_isolation" ON kpi_snapshots
    USING (
        EXISTS (
            SELECT 1 FROM datasets d
            WHERE d.id = kpi_snapshots.dataset_id
              AND d.org_id = (auth.jwt() ->> 'org_id')::uuid
        )
    );

-- ---------------------------------------------------------------------------
-- 5. audit_log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      uuid        NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id     uuid        NOT NULL REFERENCES users(id),
    -- NULL for org-level actions (e.g. login events) that aren't tied to a dataset
    dataset_id  uuid        REFERENCES datasets(id) ON DELETE SET NULL,
    -- Short action name, e.g. "upload_confirmed", "dashboard_viewed"
    action      text        NOT NULL,
    -- Structured details for frontend "why is this number what it is" display.
    -- Schema varies by action; see models.py AuditDetails for the canonical shapes.
    details     jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_log_org_isolation" ON audit_log
    USING  (org_id = (auth.jwt() ->> 'org_id')::uuid)
    WITH CHECK (org_id = (auth.jwt() ->> 'org_id')::uuid);

-- ---------------------------------------------------------------------------
-- Helpful indexes
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_datasets_org      ON datasets    (org_id);
CREATE INDEX IF NOT EXISTS idx_kpi_dataset       ON kpi_snapshots (dataset_id);
CREATE INDEX IF NOT EXISTS idx_audit_dataset     ON audit_log   (dataset_id);
CREATE INDEX IF NOT EXISTS idx_audit_org_created ON audit_log   (org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_users_org         ON users       (org_id);

-- ---------------------------------------------------------------------------
-- 6. insight_cache
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS insight_cache (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id    uuid        NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    scope         text        NOT NULL, -- 'org' | 'category'
    kpi_hash      text        NOT NULL,
    insights_json jsonb       NOT NULL,
    provider_used text        NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_insight_cache_lookup ON insight_cache (dataset_id, scope, kpi_hash);

-- ---------------------------------------------------------------------------
-- 7. usage_log (Rate limiting)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usage_log (
    id         uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action     text        NOT NULL, -- 'ask_question'
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_log_user_rate ON usage_log (user_id, action, created_at);

