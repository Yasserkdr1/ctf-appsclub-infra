#!/bin/sh
set -eu
umask 077

# All writable paths are under /tmp, mounted as an emptyDir in K3s.
mkdir -p /tmp/stream-data /tmp/stream-apache-run \
         /tmp/stream-apache-lock /tmp/stream-apache-log \
         /tmp/stream-php-sessions

rm -f /tmp/stream-data/apah.db
sqlite3 /tmp/stream-data/apah.db < /var/www/init.sql

exec apache2-foreground
