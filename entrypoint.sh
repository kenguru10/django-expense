#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
while ! pg_isready -h $DATABASE_HOST -p $DATABASE_PORT -U $POSTGRES_USER; do
    sleep 1
done

echo "Database is ready!"

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Execute main command
exec "$@"