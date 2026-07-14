-- Database Initialization Script for ContAIned Platform
-- This script runs automatically inside the postgres container on startup.

-- Create a dedicated non-superuser application user
CREATE USER contained_app_user WITH PASSWORD 'app_pass_changeme';

-- Grant connection permissions
GRANT CONNECT ON DATABASE contained_platform TO contained_app_user;

-- Grant schema modification rights in public schema for running Alembic migrations
GRANT ALL PRIVILEGES ON SCHEMA public TO contained_app_user;

-- Transfer ownership of public schema objects to the application user
ALTER SCHEMA public OWNER TO contained_app_user;
