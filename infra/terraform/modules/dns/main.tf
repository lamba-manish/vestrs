# Route53 records into the existing hosted zone for manishlamba.com.
# The zone itself is created out-of-band (or by a separate terraform
# stack); we just look it up here.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
  }
}

data "aws_route53_zone" "this" {
  name         = var.zone_name
  private_zone = false
}

# A records (IPv4) for each public hostname pointing at the EIP.
resource "aws_route53_record" "a" {
  for_each = toset(var.records)

  zone_id = data.aws_route53_zone.this.zone_id
  name    = each.value
  type    = "A"
  ttl     = 300
  records = [var.target_ip]
}
