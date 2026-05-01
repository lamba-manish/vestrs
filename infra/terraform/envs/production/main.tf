terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }

  backend "s3" {
    bucket         = "vestrs-tfstate"
    key            = "envs/production/terraform.tfstate"
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
      Env       = "production"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

data "terraform_remote_state" "bootstrap" {
  backend = "s3"
  config = {
    bucket = "vestrs-tfstate"
    key    = "bootstrap/terraform.tfstate"
    region = "ap-south-1"
  }
}

module "network" {
  source             = "../../modules/network"
  env                = "production"
  vpc_cidr           = "10.30.0.0/16"
  public_subnet_cidr = "10.30.0.0/24"
  availability_zone  = "${var.region}a"
}

module "backups" {
  source      = "../../modules/backups"
  env         = "production"
  bucket_name = var.backups_bucket_name
}

module "iam" {
  source                    = "../../modules/iam"
  env                       = "production"
  backups_bucket_arn        = module.backups.bucket_arn
  ghcr_credential_param_arn = "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter/vestrs/production/ghcr_credential"
}

locals {
  user_data = templatefile("${path.module}/../../../cloud-init/ec2-bootstrap.yaml.tpl", {
    env                   = "production"
    region                = var.region
    github_repo           = var.github_repository
    github_clone_ref      = "release/production"
    ghcr_credential_param = "/vestrs/production/ghcr_credential"
    env_file_param        = "/vestrs/production/env_file"
    pgbackups_bucket      = module.backups.bucket_name
  })
}

module "ec2" {
  source                = "../../modules/ec2"
  env                   = "production"
  vpc_id                = module.network.vpc_id
  subnet_id             = module.network.subnet_id
  instance_profile_name = module.iam.instance_profile_name
  user_data             = local.user_data
}

module "dns" {
  source    = "../../modules/dns"
  zone_name = var.dns_zone_name
  records = [
    "vestrs.${var.dns_zone_name}",
    "api.vestrs.${var.dns_zone_name}",
    "monitoring.vestrs.${var.dns_zone_name}",
  ]
  target_ip = module.ec2.elastic_ip
}

module "oidc_gha" {
  source                   = "../../modules/oidc-gha"
  env                      = "production"
  region                   = var.region
  aws_account_id           = data.aws_caller_identity.current.account_id
  target_instance_id       = module.ec2.instance_id
  github_oidc_provider_arn = data.terraform_remote_state.bootstrap.outputs.github_oidc_provider_arn
  github_repository        = var.github_repository
}
