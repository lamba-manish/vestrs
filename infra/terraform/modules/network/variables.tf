variable "env" {
  description = "Environment name — staging | production."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidr" {
  description = "CIDR block for the single public subnet."
  type        = string
  default     = "10.20.0.0/24"
}

variable "availability_zone" {
  description = "AZ for the public subnet (single AZ is sufficient — no HA in this slice)."
  type        = string
  default     = "ap-south-1a"
}
