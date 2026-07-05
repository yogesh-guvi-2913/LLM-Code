variable "region" {
  type        = string
  default     = "ap-south-1"
  description = "AWS region to deploy into (pick the one closest to your users)."
}

variable "name" {
  type        = string
  default     = "hyrenet"
  description = "Name prefix for all resources."
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC to deploy into."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for the ALB (2+ AZs)."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for the control plane + node-agent fleet."
}

variable "domain" {
  type        = string
  default     = "sandboxes.example.com"
  description = "Public hostname for the control plane / candidate API."
}

variable "acm_certificate_arn" {
  type        = string
  description = "ACM cert covering the domain AND its *.preview.<domain> wildcard (for sandbox previews). Must be in this region."
}

variable "route53_zone_id" {
  type        = string
  description = "Hosted zone id for the domain (for the A-record + wildcard preview record)."
}

variable "control_ami_id" {
  type        = string
  description = "AMI for the control-plane instance (orchestrator binary baked in, or pulled by user-data)."
}

variable "node_ami_id" {
  type        = string
  description = "Golden AMI for node-agents: Docker + gVisor (runsc) + the sandbox images pre-pulled, so L3 (new node) is ~60-90s, not a cold image pull."
}

variable "control_instance_type" {
  type    = string
  default = "t4g.medium" # control plane is I/O-light; no Docker here
}

variable "node_instance_type" {
  type        = string
  default     = "c7g.4xlarge" # 16 vCPU / 32 GB Graviton — good density-per-dollar for bursty, mostly-idle sandboxes
  description = "Sandbox-runner instance type."
}

variable "node_min" {
  type        = number
  default     = 1
  description = "Always-on baseline node count (covers walk-ins between windows)."
}

variable "node_max" {
  type        = number
  default     = 20
  description = "Ceiling the scheduled planner / target-tracking can scale to."
}

variable "sandboxes_per_node" {
  type        = number
  default     = 40
  description = "Conservative density (from /v1/usage). The control plane divides the warm target by this to publish Hyrenet/RequiredNodes."
}

variable "database_url" {
  type        = string
  sensitive   = true
  description = "Postgres DSN (RDS). Passed to the control plane."
}

variable "redis_url" {
  type        = string
  description = "Redis URL (ElastiCache) for the node registry."
}

variable "drain_timeout_sec" {
  type        = number
  default     = 1800 # 30 min: long enough for an in-progress assessment to finish
  description = "How long a node-agent waits for active sessions to finish on scale-in before exiting."
}
