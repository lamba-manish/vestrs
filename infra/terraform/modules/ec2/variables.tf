variable "env" { type = string }
variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
variable "instance_profile_name" { type = string }

variable "instance_type" {
  type    = string
  default = "t3.small"
}

variable "root_volume_gb" {
  type    = number
  default = 30
}

variable "user_data" {
  description = "Cloud-init user-data (rendered template)."
  type        = string
}
