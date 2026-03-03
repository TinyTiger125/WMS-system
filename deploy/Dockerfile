FROM odoo:19.0

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY custom/addons /mnt/extra-addons
COPY deploy/start-odoo.sh /opt/deploy/start-odoo.sh
COPY deploy/init-db.sh /opt/deploy/init-db.sh
COPY deploy/healthcheck.sh /opt/deploy/healthcheck.sh

RUN chmod +x /opt/deploy/start-odoo.sh /opt/deploy/init-db.sh /opt/deploy/healthcheck.sh \
    && chown -R odoo:odoo /mnt/extra-addons /opt/deploy

USER odoo

ENTRYPOINT ["/opt/deploy/start-odoo.sh"]
