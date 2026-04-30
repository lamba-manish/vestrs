output "instance_id" { value = module.ec2.instance_id }
output "elastic_ip" { value = module.ec2.elastic_ip }
output "dns_zone_id" { value = module.dns.zone_id }
output "deploy_role_arn" { value = module.oidc_gha.deploy_role_arn }
output "backups_bucket" { value = module.backups.bucket_name }
output "ec2_role_name" { value = module.iam.role_name }
