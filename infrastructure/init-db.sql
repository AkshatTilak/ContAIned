-- Database Initialization Script for ContAIned Platform
-- Note: Dynamic initialization with environment variables is handled via init-db.sh in docker-entrypoint-initdb.d
-- This SQL file serves as standard documentation of default schema permissions.

-- Create a dedicated non-superuser application user
-- CREATE USER contained_app_user WITH PASSWORD '${POSTGRES_PASSWORD}';

-- Grant connection permissions
GRANT CONNECT ON DATABASE contained_platform TO contained_app_user;

-- Grant schema modification rights in public schema for running Alembic migrations
GRANT ALL PRIVILEGES ON SCHEMA public TO contained_app_user;

-- Transfer ownership of public schema objects to the application user
ALTER SCHEMA public OWNER TO contained_app_user;
