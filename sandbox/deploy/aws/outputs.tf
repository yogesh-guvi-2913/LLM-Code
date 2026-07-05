output "alb_dns_name" {
  value       = aws_lb.this.dns_name
  description = "Point the domain's A-record here (done automatically via route53_zone_id)."
}

output "control_asg_name" {
  value = aws_autoscaling_group.control.name
}

output "node_asg_name" {
  value       = aws_autoscaling_group.node.name
  description = "Set ASG_NAME on the control plane to this so the planner can SetDesiredCapacity."
}

output "node_security_group_id" {
  value = aws_security_group.node.id
}

output "url" {
  value = "https://${var.domain}"
}
