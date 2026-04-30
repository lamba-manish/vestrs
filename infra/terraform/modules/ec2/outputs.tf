output "instance_id" { value = aws_instance.this.id }
output "instance_arn" { value = aws_instance.this.arn }
output "private_ip" { value = aws_instance.this.private_ip }
output "elastic_ip" { value = aws_eip.this.public_ip }
output "security_group_id" { value = aws_security_group.ec2.id }
