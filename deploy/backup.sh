#!/bin/sh
# .backup je siguran nad bazom u radu, za razliku od kopiranja datoteke.
set -eu
cd "$(dirname "$0")/.."
mkdir -p backup
sqlite3 trgovina.db ".backup 'backup/trgovina-$(date +%Y%m%d).db'"
find backup -name 'trgovina-*.db' -mtime +30 -delete
