# EC2 instance role: SSM core (Session Manager + RunCommand),
# CloudWatch agent, and read/write to the env's pg_dump bucket.
# That last bit is appended via aws_iam_role_policy at the env level,
# since the bucket name is module output.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "vestrs-${var.env}-ec2"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
  tags               = { Name = "vestrs-${var.env}-ec2" }
}

# Session Manager + RunCommand — replaces public SSH entirely.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# CloudWatch agent — host-level metrics + log forwarding (slice 14C).
resource "aws_iam_role_policy_attachment" "cw_agent" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# Inline policy bound to the bucket the env stack provisions.
resource "aws_iam_role_policy" "backups" {
  count  = var.backups_bucket_arn == null ? 0 : 1
  name   = "vestrs-${var.env}-ec2-backups"
  role   = aws_iam_role.ec2.id
  policy = data.aws_iam_policy_document.backups[0].json
}

data "aws_iam_policy_document" "backups" {
  count = var.backups_bucket_arn == null ? 0 : 1

  statement {
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:DeleteObject",
    ]
    resources = [
      var.backups_bucket_arn,
      "${var.backups_bucket_arn}/*",
    ]
  }
}

# GHCR pulls. The instance authenticates to GHCR with a PAT stored in
# SSM Parameter Store (slice 14B writes the param name here so cloud-init
# can retrieve it). The role needs read access to that one parameter.
resource "aws_iam_role_policy" "ghcr_pull" {
  count = var.ghcr_credential_param_arn == null ? 0 : 1
  name  = "vestrs-${var.env}-ec2-ghcr"
  role  = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = [
          var.ghcr_credential_param_arn,
        ]
      },
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "vestrs-${var.env}-ec2"
  role = aws_iam_role.ec2.name
}
