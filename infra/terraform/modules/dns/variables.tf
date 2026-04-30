variable "zone_name" {
  description = "Existing Route53 hosted zone (e.g. manishlamba.com)."
  type        = string
}

variable "records" {
  description = "FQDNs to point at target_ip (e.g. [\"vestrs.manishlamba.com\", \"api.vestrs.manishlamba.com\"])."
  type        = set(string)
}

variable "target_ip" {
  description = "Public IP (the EC2 EIP)."
  type        = string
}
