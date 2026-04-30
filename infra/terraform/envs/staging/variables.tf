variable "region" {
  type    = string
  default = "ap-south-1"
}

variable "dns_zone_name" {
  type    = string
  default = "manishlamba.com"
}

variable "github_repository" {
  type    = string
  default = "lamba-manish/vestrs"
}

variable "backups_bucket_name" {
  description = "Globally-unique S3 bucket name for the staging pg_dump artifacts."
  type        = string
}
