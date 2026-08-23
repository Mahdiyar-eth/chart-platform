-- R4/W5: create the pgvector extension at container boot, as the postgres
-- superuser (the entrypoint runs this as superuser before the app connects).
-- Without this, the first CREATE_ALL_ON_BOOT (conftest init_db) hits
-- "permission denied to create extension vector" because the health-check dir
-- runs the connection user, not the superuser.
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON SCHEMA public TO chart_test;
