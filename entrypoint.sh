#!/bin/sh
# Seed the data directory from baked-in DB if no existing DB found
if [ ! -f /app/data/kanji-srs.db ]; then
    echo "Seeding database from image..."
    cp /app/data-seed/kanji-srs.db /app/data/kanji-srs.db
fi

exec "$@"
