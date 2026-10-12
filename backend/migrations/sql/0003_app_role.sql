-- D-059 P2: the app works as `sharksight_app`, not as the owner. Append-only tables are protected by permission, not
-- only by trigger: the app role has no UPDATE / DELETE / TRUNCATE on them, and cannot change the schema. Migrations,
-- backups and admin scripts use the owner (MIGRATION_DATABASE_URL). The login password is set by the migration from
-- APP_DB_PASSWORD (migrations/versions/0003_app_role.py); roles are cluster-wide, grants are per database.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sharksight_app') THEN
    CREATE ROLE sharksight_app NOLOGIN;
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO sharksight_app', current_database());
END $$;

GRANT USAGE ON SCHEMA public TO sharksight_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sharksight_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sharksight_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_event, def_choice, def_link_review, prio_decision FROM sharksight_app;
REVOKE ALL ON alembic_version FROM sharksight_app;

-- tables and sequences created by later migrations (run as the owner) get the same default grants; a new append-only
-- table must REVOKE UPDATE, DELETE in its own migration
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sharksight_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO sharksight_app;
