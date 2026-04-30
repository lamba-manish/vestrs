# One-time bootstrap — creates the S3 bucket + DynamoDB table that
# every other terraform stack uses for remote state.
#
# Why a separate stack? Chicken-and-egg: the main stacks store their
# state in this bucket, so this bucket must exist (and be terraformed)
# before they run. We keep this stack's state in S3 too — but in a
# different key so it can recover its own infrastructure.
#
# Usage (one-time per AWS account):
#   cd infra/terraform/bootstrap
#   terraform init
#   terraform apply
#
# Subsequent edits to the bootstrap stack are rare; when they happen,
# run `terraform apply` here again.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # First apply runs against a local backend; once the bucket exists,
  # uncomment the block below + `terraform init -migrate-state`.
  #
  # backend "s3" {
  #   bucket         = "vestrs-tfstate"
  #   key            = "bootstrap/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "vestrs-tfstate-lock"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = "vestrs"
      Env       = "bootstrap"
      ManagedBy = "terraform"
    }
  }
}

# ---------- state bucket ----------

resource "aws_s3_bucket" "state" {
  bucket = var.state_bucket_name
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Cheap insurance against an accidental `terraform destroy` of state.
resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    id     = "expire-noncurrent-after-180-days"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration { noncurrent_days = 180 }
  }
}

# ---------- lock table ----------

resource "aws_dynamodb_table" "lock" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  point_in_time_recovery { enabled = true }
}

# ---------- GitHub Actions OIDC provider (account-wide singleton) ----------
#
# Per-env stacks reference this via data lookup and only create their
# own role. Splitting the provider out of those stacks avoids the
# collision when both staging and production try to create the same
# global resource.

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]

  tags = { Project = "vestrs" }
}
