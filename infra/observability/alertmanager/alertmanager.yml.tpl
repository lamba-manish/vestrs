# Alertmanager config (slice 25).
#
# Single email receiver for now. Both severity levels (`page` and
# `ticket`) route to the same inbox; we can split later by adding a
# Slack/PagerDuty receiver and a per-severity route. The 5-minute
# group_interval prevents email floods if a flapping alert fires
# repeatedly.
#
# SMTP credentials come from environment (loaded via .env.production):
#   ALERTMANAGER_SMTP_HOST       e.g. smtp.gmail.com:587
#   ALERTMANAGER_SMTP_USERNAME   gmail address
#   ALERTMANAGER_SMTP_PASSWORD   gmail app password (NOT the account pw)
#   ALERTMANAGER_EMAIL_TO        recipient (manishlamba002@gmail.com)
#
# To enable, generate a Google App Password
# (https://myaccount.google.com/apppasswords) and store it in SSM as
# /vestrs/production/ALERTMANAGER_SMTP_PASSWORD; deploy.sh re-renders
# .env.production from SSM at deploy time.

global:
  resolve_timeout: 5m
  smtp_smarthost: "${ALERTMANAGER_SMTP_HOST}"
  smtp_from: "${ALERTMANAGER_SMTP_USERNAME}"
  smtp_auth_username: "${ALERTMANAGER_SMTP_USERNAME}"
  smtp_auth_password: "${ALERTMANAGER_SMTP_PASSWORD}"
  smtp_require_tls: true

route:
  receiver: email-default
  group_by: ["alertname", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - matchers: [severity="page"]
      receiver: email-default
      group_wait: 0s
      repeat_interval: 1h

receivers:
  - name: email-default
    email_configs:
      - to: "${ALERTMANAGER_EMAIL_TO}"
        send_resolved: true
        headers:
          Subject: "[Vestrs · {{ .Status | toUpper }}] {{ .CommonLabels.alertname }} ({{ .CommonLabels.severity }})"

inhibit_rules:
  # If the whole instance is down, suppress the per-route alerts that
  # depend on it — otherwise one outage triggers a swarm of duplicates.
  - source_matchers: [alertname="InstanceDown"]
    target_matchers: [severity=~"page|ticket"]
    equal: ["instance"]
