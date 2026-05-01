terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }

  backend "s3" {
    bucket         = "vestrs-tfstate"
    key            = "envs/staging/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "vestrs-tfstate-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project   = "vestrs"
      Env       = "staging"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

# ---------- shared bootstrap state (OIDC provider ARN) ----------
data "terraform_remote_state" "bootstrap" {
  backend = "s3"
  config = {
    bucket = "vestrs-tfstate"
    key    = "bootstrap/terraform.tfstate"
    region = "ap-south-1"
  }
}

# ---------- network ----------
module "network" {
  source             = "../../modules/network"
  env                = "staging"
  vpc_cidr           = "10.20.0.0/16"
  public_subnet_cidr = "10.20.0.0/24"
  availability_zone  = "${var.region}a"
}

# ---------- backups ----------
module "backups" {
  source      = "../../modules/backups"
  env         = "staging"
  bucket_name = var.backups_bucket_name
}

# ---------- iam (ec2 instance role) ----------
module "iam" {
  source                    = "../../modules/iam"
  env                       = "staging"
  backups_bucket_arn        = module.backups.bucket_arn
  ghcr_credential_param_arn = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/vestrs/staging/ghcr_credential"
}

# ---------- cloud-init ----------
locals {
  user_data = templatefile("${path.module}/../../../cloud-init/ec2-bootstrap.yaml.tpl", {
    env                   = "staging"
    region                = var.region
    github_repo           = var.github_repository
    github_clone_ref      = "release/staging"
    ghcr_credential_param = "/vestrs/staging/ghcr_credential"
    env_file_param        = "/vestrs/staging/env_file"
    pgbackups_bucket      = module.backups.bucket_name
  })
}

# ---------- ec2 ----------
module "ec2" {
  source                = "../../modules/ec2"
  env                   = "staging"
  vpc_id                = module.network.vpc_id
  subnet_id             = module.network.subnet_id
  instance_profile_name = module.iam.instance_profile_name
  user_data             = local.user_data
}

# ---------- dns ----------
module "dns" {
  source    = "../../modules/dns"
  zone_name = var.dns_zone_name
  records = [
    "staging.vestrs.${var.dns_zone_name}",
    "staging-api.vestrs.${var.dns_zone_name}",
  ]
  target_ip = module.ec2.elastic_ip
}

# ---------- gha deploy role ----------
module "oidc_gha" {
  source                   = "../../modules/oidc-gha"
  env                      = "staging"
  region                   = var.region
  aws_account_id           = data.aws_caller_identity.current.account_id
  github_oidc_provider_arn = data.terraform_remote_state.bootstrap.outputs.github_oidc_provider_arn
  github_repository        = var.github_repository
}
