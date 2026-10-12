-- D-059 P2: native types where the database should understand the value.
-- 1. System timestamps (set by the database or the app, never copied from a source) become timestamptz. Defaults use
--    statement_timestamp(): like SQLite's 'now', it differs per statement inside one transaction (now() would not, and
--    rows written in one transaction would tie and change their order). Source dates (published_at, cutoff) stay TEXT:
--    they can be partial ("2026-01"). The app reads timestamptz back as the same ISO text (bmw_req.db loader).
-- 2. weights_version.weights_json becomes jsonb: it is the one JSON column queried in SQL (->> 'scheme').
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT table_name AS t, column_name AS c, column_default IS NOT NULL AS has_default
           FROM information_schema.columns
           WHERE table_schema = current_schema()
             AND (column_default LIKE '%utc_now_text%'
                  OR (table_name, column_name) IN (('llm_usage', 'settled_at'), ('checkpoint_run', 'finished_at'),
                                                   ('prio_proposal', 'decided_at')))
  LOOP
    EXECUTE format('ALTER TABLE %I ALTER COLUMN %I DROP DEFAULT', r.t, r.c);
    EXECUTE format('ALTER TABLE %I ALTER COLUMN %I TYPE timestamptz USING %I::timestamptz', r.t, r.c, r.c);
    IF r.has_default THEN
      EXECUTE format('ALTER TABLE %I ALTER COLUMN %I SET DEFAULT statement_timestamp()', r.t, r.c);
    END IF;
  END LOOP;
END $$;

ALTER TABLE weights_version ALTER COLUMN weights_json TYPE jsonb USING weights_json::jsonb;

-- the timestamp the app wrote as text before P2; kept for anything still comparing text
CREATE OR REPLACE FUNCTION utc_now_text() RETURNS text LANGUAGE sql STABLE
    AS $$ SELECT to_char(statement_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"') $$;
