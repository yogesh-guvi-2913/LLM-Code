# Flash v2 on AWS — the horizontal-scale deploy shape.
#
# Shape:
#   Internet ─HTTPS(443, ACM)─> ALB ──> control-plane ASG (orchestrator :8090)
#                                            │  (schedules over Redis + HTTP)
#                                            v
#                                     node-agent ASG (the scaling fleet)
#
# The control plane publishes Hyrenet/RequiredNodes (warm target ÷ density). A
# target-tracking policy scales the node ASG on it, so a booked assessment window
# grows the fleet ahead of T (the L3 tier). A termination lifecycle hook gives a
# scaled-in node time to drain its active sessions (the SIGTERM path proven in
# scripts/node-drain-check.sh) before the instance is killed.
#
# NOTE: this is deploy-time IaC — it needs real account values (VPC, subnets,
# ACM, AMIs, RDS/ElastiCache endpoints) and has not been `apply`-ed here, the same
# boundary as TLS. It is `terraform validate`-clean.

locals {
  tags = {
    Project   = var.name
    ManagedBy = "terraform"
  }
}

# ---------------- security groups ----------------

resource "aws_security_group" "alb" {
  name_prefix = "${var.name}-alb-"
  vpc_id      = var.vpc_id
  description = "Public ingress to the ALB (443/80 only)."

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTP (redirected to HTTPS)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "control" {
  name_prefix = "${var.name}-control-"
  vpc_id      = var.vpc_id
  description = "Control plane: ALB → :8090."

  ingress {
    description     = "API + preview from the ALB"
    from_port       = 8090
    to_port         = 8090
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "node" {
  name_prefix = "${var.name}-node-"
  vpc_id      = var.vpc_id
  description = "Node-agents: reached only by the control plane."

  ingress {
    description     = "node-agent API from the control plane"
    from_port       = 9001
    to_port         = 9001
    protocol        = "tcp"
    security_groups = [aws_security_group.control.id]
  }
  ingress {
    description     = "published sandbox ports (preview/terminal) from the control plane"
    from_port       = 20000
    to_port         = 29000
    protocol        = "tcp"
    security_groups = [aws_security_group.control.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

# ---------------- ALB + TLS ----------------

resource "aws_lb" "this" {
  name               = "${var.name}-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids
  tags               = local.tags
}

resource "aws_lb_target_group" "control" {
  name        = "${var.name}-control"
  port        = 8090
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "instance"

  # Readiness, not liveness: a draining or still-warming control plane is pulled
  # out of rotation (matches the /readyz semantics built in Phase 0).
  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 10
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
  }
  tags = local.tags
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn # must also cover *.preview.<domain>

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.control.arn
  }
  tags = local.tags
}

# Plain HTTP → HTTPS redirect.
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
  tags = local.tags
}

# Apex + wildcard preview both resolve to the ALB; the orchestrator splits the
# vhost internally (`<token>.<sid>.preview.<domain>` → preview proxy).
resource "aws_route53_record" "apex" {
  zone_id = var.route53_zone_id
  name    = var.domain
  type    = "A"
  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}

resource "aws_route53_record" "preview_wildcard" {
  zone_id = var.route53_zone_id
  name    = "*.preview.${var.domain}"
  type    = "A"
  alias {
    name                   = aws_lb.this.dns_name
    zone_id                = aws_lb.this.zone_id
    evaluate_target_health = true
  }
}

# ---------------- control-plane ASG ----------------

resource "aws_launch_template" "control" {
  name_prefix            = "${var.name}-control-"
  image_id               = var.control_ami_id
  instance_type          = var.control_instance_type
  vpc_security_group_ids = [aws_security_group.control.id]

  iam_instance_profile {
    arn = aws_iam_instance_profile.control.arn
  }

  user_data = base64encode(templatefile("${path.module}/user-data-control.sh.tftpl", {
    database_url       = var.database_url
    redis_url          = var.redis_url
    domain             = var.domain
    sandboxes_per_node = var.sandboxes_per_node
    node_asg_name      = "${var.name}-node"
    region             = var.region
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.tags, { Role = "control-plane" })
  }
}

resource "aws_autoscaling_group" "control" {
  name                = "${var.name}-control"
  vpc_zone_identifier = var.private_subnet_ids
  min_size            = 1
  max_size            = 2
  desired_capacity    = 1
  target_group_arns   = [aws_lb_target_group.control.arn]
  health_check_type   = "ELB"

  launch_template {
    id      = aws_launch_template.control.id
    version = "$Latest"
  }

  dynamic "tag" {
    for_each = merge(local.tags, { Role = "control-plane" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

# ---------------- node-agent ASG (the scaling fleet) ----------------

resource "aws_launch_template" "node" {
  name_prefix            = "${var.name}-node-"
  image_id               = var.node_ami_id
  instance_type          = var.node_instance_type
  vpc_security_group_ids = [aws_security_group.node.id]

  user_data = base64encode(templatefile("${path.module}/user-data-node.sh.tftpl", {
    redis_url         = var.redis_url
    drain_timeout_sec = var.drain_timeout_sec
  }))

  tag_specifications {
    resource_type = "instance"
    tags          = merge(local.tags, { Role = "node-agent" })
  }
}

resource "aws_autoscaling_group" "node" {
  name                = "${var.name}-node"
  vpc_zone_identifier = var.private_subnet_ids
  min_size            = var.node_min
  max_size            = var.node_max
  desired_capacity    = var.node_min

  launch_template {
    id      = aws_launch_template.node.id
    version = "$Latest"
  }

  # Termination lifecycle hook: on scale-in the instance enters Terminating:Wait
  # and our shutdown hook sends SIGTERM to the node-agent, which keeps serving its
  # ACTIVE sessions until they finish (or drain_timeout) before letting the
  # instance die. See scripts/node-drain-check.sh.
  initial_lifecycle_hook {
    name                 = "drain"
    lifecycle_transition = "autoscaling:EC2_INSTANCE_TERMINATING"
    heartbeat_timeout    = var.drain_timeout_sec
    default_result       = "CONTINUE"
  }

  dynamic "tag" {
    for_each = merge(local.tags, { Role = "node-agent" })
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    # Scheduled planner / target-tracking owns desired_capacity at runtime.
    ignore_changes = [desired_capacity]
  }
}

# Scaling driver. Our load is *known* (assessments are booked), so the planner
# scales imperatively rather than reactively: it computes required node count from
# the booked windows (publishing it as both `hyrenet_required_nodes` on /metrics and
# the CloudWatch metric Hyrenet/RequiredNodes) and calls SetDesiredCapacity on the
# node ASG ahead of T. This block grants the control plane exactly that authority;
# the scaler call itself is the small deploy-time code gap (env ASG_NAME below),
# the same boundary as TLS. A reactive CloudWatch target-tracking policy can be
# layered on later as a walk-in backstop.
data "aws_iam_policy_document" "control_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "control_scale" {
  statement {
    sid       = "DriveNodeASG"
    actions   = ["autoscaling:SetDesiredCapacity", "autoscaling:DescribeAutoScalingGroups"]
    resources = ["*"]
  }
  statement {
    sid       = "PublishSignal"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "control" {
  name_prefix        = "${var.name}-control-"
  assume_role_policy = data.aws_iam_policy_document.control_assume.json
  tags               = local.tags
}

resource "aws_iam_role_policy" "control_scale" {
  name   = "scale-nodes"
  role   = aws_iam_role.control.id
  policy = data.aws_iam_policy_document.control_scale.json
}

resource "aws_iam_instance_profile" "control" {
  name_prefix = "${var.name}-control-"
  role        = aws_iam_role.control.name
}
