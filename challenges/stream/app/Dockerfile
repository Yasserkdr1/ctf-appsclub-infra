FROM php:8.2-apache-bookworm

# Apache runtime paths for non-root + read-only filesystem
ENV APACHE_RUN_USER=ctf \
    APACHE_RUN_GROUP=ctf \
    APACHE_RUN_DIR=/tmp/stream-apache-run \
    APACHE_LOCK_DIR=/tmp/stream-apache-lock \
    APACHE_LOG_DIR=/tmp/stream-apache-log \
    APACHE_PID_FILE=/tmp/stream-apache-run/apache2.pid


RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends sqlite3 libsqlite3-dev; \
    docker-php-ext-install pdo_sqlite; \
    a2enmod rewrite; \
    rm -rf /var/lib/apt/lists/*

# Apache listens on an unprivileged port; the whole container runs as UID 10001.
RUN set -eux; \
    groupadd -g 10001 ctf; \
    useradd -r -M -u 10001 -g 10001 -s /usr/sbin/nologin ctf; \
    sed -ri 's/^Listen 80$/Listen 8080/' /etc/apache2/ports.conf; \
    sed -ri 's/<VirtualHost \*:80>/<VirtualHost *:8080>/' /etc/apache2/sites-available/000-default.conf; \
    sed -ri 's@^export APACHE_RUN_USER=.*@export APACHE_RUN_USER=ctf@' /etc/apache2/envvars; \
    sed -ri 's@^export APACHE_RUN_GROUP=.*@export APACHE_RUN_GROUP=ctf@' /etc/apache2/envvars; \
    sed -ri 's@^export APACHE_PID_FILE=.*@export APACHE_PID_FILE=/tmp/stream-apache-run/apache2.pid@' /etc/apache2/envvars; \
    sed -ri 's@^export APACHE_RUN_DIR=.*@export APACHE_RUN_DIR=/tmp/stream-apache-run@' /etc/apache2/envvars; \
    sed -ri 's@^export APACHE_LOCK_DIR=.*@export APACHE_LOCK_DIR=/tmp/stream-apache-lock@' /etc/apache2/envvars; \
    sed -ri 's@^export APACHE_LOG_DIR=.*@export APACHE_LOG_DIR=/tmp/stream-apache-log@' /etc/apache2/envvars; \
    printf '%s\n' 'ServerName localhost' > /etc/apache2/conf-available/stream-servername.conf; \
    a2enconf stream-servername; \
    printf '%s\n' 'session.save_path = "/tmp/stream-php-sessions"' > /usr/local/etc/php/conf.d/zz-stream-sessions.ini; \
    ln -s /tmp/stream-data /var/www/data

# Keep the intentional SQL injection in search.php unchanged.
COPY src/ /var/www/html/
COPY db/init.sql /var/www/init.sql
COPY entrypoint.sh /entrypoint.sh

RUN chmod 0555 /entrypoint.sh && \
    chmod -R a-w /var/www/html && \
    chmod a+r /var/www/init.sql

USER 10001:10001
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
