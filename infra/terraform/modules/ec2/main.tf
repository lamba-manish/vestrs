# Single t3.small running everything: Caddy, FastAPI, ARQ worker,
# Postgres 16, Redis 7, grafana-agent (slice 14C). 2GB RAM with a 2GB
# swapfile from cloud-init.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

# ---------- security group ----------

resource "aws_security_group" "ec2" {
  name        = "vestrs-${var.env}-ec2"
  description = "vestrs ${var.env} - public 80/443 only; SSH closed."
  vpc_id      = var.vpc_id

  ingress {
    description      = "HTTP"
    from_port        = 80
    to_port          = 80
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  ingress {
    description      = "HTTPS"
    from_port        = 443
    to_port          = 443
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    description      = "all outbound"
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = { Name = "vestrs-${var.env}-ec2" }
}

# ---------- AMI ----------

# Canonical's Ubuntu 24.04 LTS, x86_64, hvm:ebs-ssd-gp3.
data "aws_ami" "ubuntu_2404" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

# ---------- instance ----------

resource "aws_instance" "this" {
  ami                    = data.aws_ami.ubuntu_2404.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = var.instance_profile_name

  user_data                   = var.user_data
  user_data_replace_on_change = true

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_endpoint               = "enabled"
    http_put_response_hop_limit = 2
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_gb
    encrypted   = true
  }

  monitoring = false # detailed monitoring costs $; basic 5-min metrics are free

  tags = {
    Name = "vestrs-${var.env}"
    Env  = var.env
  }
}

resource "aws_eip" "this" {
  instance = aws_instance.this.id
  domain   = "vpc"
  tags     = { Name = "vestrs-${var.env}" }
}
