-- Run once in the twin as the postgres superuser: a login for the dbt job, read-only on accounting (D27).
-- docker exec -i astronomy-db psql -U postgres -d astronomy_db -v pw="'<password>'" < setup.sql
CREATE ROLE analytics_dbt LOGIN PASSWORD :pw;
GRANT USAGE ON SCHEMA accounting TO analytics_dbt;
GRANT SELECT ON ALL TABLES IN SCHEMA accounting TO analytics_dbt;
GRANT CREATE ON DATABASE astronomy_db TO analytics_dbt;
