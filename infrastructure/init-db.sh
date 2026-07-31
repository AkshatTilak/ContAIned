#!/bin/bash
set -e

# Database Initialization Script for ContAIned Platform
# Reads environment variables passed to the postgres container on startup.

APP_USER="${POSTGRES_APP_USER:-contained_app_user}"
APP_PASS="${POSTGRES_APP_PASSWORD:-${POSTGRES_PASSWORD:-contained_pass}}"
DB_NAME="${POSTGRES_DB:-contained_platform}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$APP_USER') THEN
            CREATE USER $APP_USER WITH PASSWORD '$APP_PASS';
        ELSE
            ALTER USER $APP_USER WITH PASSWORD '$APP_PASS';
        END IF;
    END
    \$\$;

    GRANT CONNECT ON DATABASE "$DB_NAME" TO $APP_USER;
    GRANT ALL PRIVILEGES ON SCHEMA public TO $APP_USER;
    ALTER SCHEMA public OWNER TO $APP_USER;
EOSQL
