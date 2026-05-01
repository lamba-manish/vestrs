# Per-env GitHub Actions deploy role. Trusts a fixed `sub` so only
# the matching `release/<env>` branch (or the matching GitHub
# Environment) can assume it.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [var.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:ref:refs/heads/release/${var.env}",
        "repo:${var.github_repository}:environment:${var.env}",
      ]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "vestrs-${var.env}-gha-deploy"
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  max_session_duration = 3600
  tags                 = { Env = var.env }
}

# Permissions: SSM SendCommand restricted by EC2 tag (Env=<env>) plus
# the read-side APIs needed to track command progress.
#
# We previously pinned the SendCommand resource to a specific
# instance ARN (var.target_instance_id). That broke whenever the EC2
# was rebuilt — the role still authorised SSM only on the destroyed
# instance id, and CI deploys 403'd until a manual terraform apply
# re-rendered the policy. Tag-based scoping is the AWS-recommended
# pattern for "this role can SSM into any host belonging to env X"
# without the rebuild-drift footgun.
#
# All EC2 instances created by infra/terraform/modules/ec2/ already
# carry { Name = "vestrs-<env>", Env = <env> }, so the condition is
# strictly equivalent in practice but survives rebuilds.
data "aws_iam_policy_document" "deploy" {
  statement {
    sid     = "SsmSendCommandToEnvInstances"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ec2:${var.region}:${var.aws_account_id}:instance/*",
    ]
    condition {
      test     = "StringEquals"
      variable = "aws:ResourceTag/Env"
      values   = [var.env]
    }
  }

  statement {
    sid     = "SsmSendCommandDocument"
    actions = ["ssm:SendCommand"]
    resources = [
      "arn:aws:ssm:${var.region}::document/AWS-RunShellScript",
    ]
  }

  statement {
    sid       = "SsmTrackCommand"
    actions   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:DescribeInstanceInformation"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
  name   = "deploy"
}
