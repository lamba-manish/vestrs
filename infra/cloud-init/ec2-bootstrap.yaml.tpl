#cloud-config
# Vestrs EC2 bootstrap.
#
# Renders into the instance user-data. Variables interpolated by
# terraform's `templatefile()`:
#
#   env                       — staging | production
#   github_repo               — lamba-manish/vestrs
#   github_clone_ref          — branch to clone (release/staging | release/production)
#   ghcr_credential_param     — SSM Parameter Store name holding the GHCR PAT
#                                (so cloud-init can `docker login ghcr.io`)
#   compose_file              — relative path inside the repo
#                                (infra/compose/docker-compose.<env>.yml)
#   env_file_param            — SSM Parameter Store name holding the .env file
#                                content (read at boot, written to /opt/vestrs/.env.<env>)
#   pgbackups_bucket          — S3 bucket name for nightly pg_dump uploads
#   region                    — AWS region (for awscli)

package_update: true
package_upgrade: true

packages:
  - ca-certificates
  - curl
  - git
  - gnupg
  - lsb-release
  - ufw
  - fail2ban
  - unzip
  - unattended-upgrades
  - jq
  # Note: Ubuntu 24.04 (noble) dropped the deprecated `awscli` (v1)
  # package from the base repos. AWS CLI v2 is installed from the
  # official tarball in `runcmd` below.

users:
  # Operator login is via SSM Session Manager, which uses ssm-user.
  # `deploy` is the service account that owns /opt/vestrs and runs
  # docker compose; it has no password and no SSH key.
  - name: deploy
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    groups: [docker]
    lock_passwd: true

write_files:
  # Sysctl: a small swappiness so the 2GB swapfile is only used under
  # genuine pressure, not casual cache reclaim.
  - path: /etc/sysctl.d/99-vestrs.conf
    content: |
      vm.swappiness = 10
      net.core.somaxconn = 4096
      net.ipv4.tcp_tw_reuse = 1

  # Disable password auth + root SSH login (defence in depth — the
  # security group already blocks 22 from the internet, so SSH is
  # only reachable inside the VPC).
  - path: /etc/ssh/sshd_config.d/00-hardening.conf
    content: |
      PasswordAuthentication no
      PermitRootLogin no
      ChallengeResponseAuthentication no

  # fail2ban — Caddy log jail. Bans IPs that hit 401/403/429/repeated
  # 404s. Caddy writes JSON logs to stdout (compose journald) so we
  # mirror them onto /var/log/caddy/access.log via a tiny tail.
  - path: /etc/fail2ban/filter.d/caddy-auth.conf
    content: |
      [Definition]
      failregex = .*"remote_ip":"<HOST>".*"status":(401|403|429).*
      ignoreregex =
  - path: /etc/fail2ban/jail.d/caddy.conf
    content: |
      [caddy-auth]
      enabled  = true
      port     = http,https
      filter   = caddy-auth
      logpath  = /var/log/caddy/access.log
      backend  = polling
      maxretry = 12
      findtime = 600
      bantime  = 900

  # Backup script — pg_dump → gzip → s3 cp. Run nightly via systemd
  # timer below.
  - path: /usr/local/bin/vestrs-pgbackup
    permissions: "0755"
    content: |
      #!/usr/bin/env bash
      set -euo pipefail
      ENV="${env}"
      BUCKET="${pgbackups_bucket}"
      TS=$(date -u +%FT%H%M%SZ)
      KEY="$ENV/$TS.sql.gz"
      cd /opt/vestrs
      docker compose -f infra/compose/docker-compose.$ENV.yml --env-file .env.$ENV \
        exec -T postgres \
        pg_dump --no-owner --no-privileges -U "$$POSTGRES_USER" "$$POSTGRES_DB" \
        | gzip -9 \
        | aws s3 cp - "s3://$BUCKET/$KEY" --region ${region} \
            --storage-class STANDARD_IA \
            --metadata "instance=$(hostname),env=$ENV"
      echo "backup ok: s3://$BUCKET/$KEY"

  # systemd timer — every day 03:17 UTC (light off-peak).
  - path: /etc/systemd/system/vestrs-pgbackup.service
    content: |
      [Unit]
      Description=Vestrs Postgres backup → S3
      After=docker.service network-online.target
      Wants=network-online.target
      [Service]
      Type=oneshot
      User=root
      ExecStart=/usr/local/bin/vestrs-pgbackup
  - path: /etc/systemd/system/vestrs-pgbackup.timer
    content: |
      [Unit]
      Description=Run vestrs-pgbackup nightly
      [Timer]
      OnCalendar=*-*-* 03:17:00 UTC
      Persistent=true
      [Install]
      WantedBy=timers.target

runcmd:
  # ----- swap (2GB) -----
  - |
    if ! grep -q '/swapfile' /etc/fstab; then
      fallocate -l 2G /swapfile
      chmod 600 /swapfile
      mkswap /swapfile
      swapon /swapfile
      echo '/swapfile none swap sw 0 0' >> /etc/fstab
    fi

  # ----- AWS CLI v2 (Ubuntu 24.04 dropped awscli v1 from base) -----
  - |
    if ! command -v aws >/dev/null; then
      curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
      unzip -q -o /tmp/awscliv2.zip -d /tmp
      /tmp/aws/install --update
      rm -rf /tmp/aws /tmp/awscliv2.zip
    fi

  # ----- docker (single shell block keeps the heredoc + escape clean) -----
  - |
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    CODENAME=$(. /etc/os-release && echo "$VERSION_CODENAME")
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $CODENAME stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    usermod -aG docker deploy

  # ----- ufw -----
  - ufw default deny incoming
  - ufw default allow outgoing
  - ufw allow 80/tcp
  - ufw allow 443/tcp
  - ufw --force enable

  # ----- ssh hardening -----
  - systemctl reload ssh

  # ----- repo clone -----
  - mkdir -p /opt/vestrs
  - chown deploy:deploy /opt/vestrs
  - sudo -u deploy git clone --depth=1 --branch=${github_clone_ref} https://github.com/${github_repo}.git /opt/vestrs

  # ----- env file from SSM Parameter Store -----
  - |
    aws ssm get-parameter \
      --region ${region} \
      --name '${env_file_param}' \
      --with-decryption \
      --query 'Parameter.Value' --output text \
      > /opt/vestrs/.env.${env}
    chown deploy:deploy /opt/vestrs/.env.${env}
    chmod 600 /opt/vestrs/.env.${env}

  # ----- GHCR docker login -----
  - |
    GHCR_PAT=$(aws ssm get-parameter \
      --region ${region} \
      --name '${ghcr_credential_param}' \
      --with-decryption \
      --query 'Parameter.Value' --output text)
    GHCR_USER=$(echo "$GHCR_PAT" | cut -d: -f1)
    GHCR_TOKEN=$(echo "$GHCR_PAT" | cut -d: -f2-)
    sudo -u deploy bash -c "echo '$GHCR_TOKEN' | docker login ghcr.io -u '$GHCR_USER' --password-stdin"

  # ----- caddy log directory (fail2ban tails it) -----
  - mkdir -p /var/log/caddy
  - chown 1000:1000 /var/log/caddy

  # ----- enable backup timer -----
  - systemctl daemon-reload
  - systemctl enable --now vestrs-pgbackup.timer

  # ----- fail2ban -----
  - systemctl enable --now fail2ban

  # ----- first compose up -----
  - sudo -u deploy bash -c "cd /opt/vestrs && bash infra/scripts/deploy.sh ${env}"

final_message: "vestrs ${env} bootstrap complete in $UPTIME seconds"
