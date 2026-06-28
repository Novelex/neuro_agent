#!/bin/sh
set -e

# Run migrations if database is ready
echo "Checking and running database migrations..."
alembic upgrade head

# Execute the main container process (passed in CMD)
exec "$@"
