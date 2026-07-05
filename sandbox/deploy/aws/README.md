# Flash v2 on AWS (Terraform)

The horizontal-scale deploy shape — the parts that need a real AWS account (VPC,
ACM, AMIs, RDS/ElastiCache) and so cannot be run on a laptop, the same boundary
as TLS. The config is `terraform validate`-clean.

```
Internet ─HTTPS:443 (ACM)─▶ ALB ─▶ control-plane ASG (orchestrator :8090, CLUSTER mode)
                                          │  schedules over Redis + HTTP
                                          ▼
                                   node-agent ASG  ← scaling fleet (c7g.4xlarge)
```

## What it provisions

| Resource | Why |
|---|---|
| ALB + HTTPS listener (ACM) + HTTP→HTTPS redirect | TLS termination for the control-plane domain |
| Route53 apex A-record **and** `*.preview.<domain>` | sandbox previews resolve to the same ALB; the orchestrator splits the vhost |
| Target group health check on **`/readyz`** | a draining/warming box is pulled from rotation |
| Control-plane ASG (no Docker) | runs the orchestrator in `CLUSTER_MODE=true` |
| Node-agent ASG (`min`..`max`) | the sandbox fleet; golden AMI = Docker + gVisor + images pre-pulled (L3 ≈ 60–90s) |
| **Termination lifecycle hook → drain** | scale-in SIGTERMs the node-agent, which finishes ACTIVE sessions before the instance dies (`scripts/node-drain-check.sh`) |
| IAM role for the control plane | `autoscaling:SetDesiredCapacity` + `cloudwatch:PutMetricData` so the planner drives node count |

## The scaling loop (L1/L2 built, L3 scaffolded)

The planner (in the control plane, **already built and proven** —
`scripts/window-check.sh`) computes, from the booked `assessment_windows`:

- **warm floor per template** → `SetMinWarm` (L1 instant claims / L2 top-ups). ✅ live
- **`flash_required_nodes`** = ⌈warm target ÷ `SANDBOXES_PER_NODE`⌉, exported on
  `/metrics`. ✅ live

The remaining deploy-time gap (the "scaler") is a few lines wiring that number to
`autoscaling:SetDesiredCapacity` on `node_asg_name` (env `ASG_NAME`, IAM already
granted here) and `PutMetricData` for `Flash/RequiredNodes`. That is the only
piece that needs the AWS SDK + a live account — everything it depends on is done.

## Apply

```bash
terraform init
terraform apply \
  -var vpc_id=vpc-xxxx \
  -var 'public_subnet_ids=["subnet-a","subnet-b"]' \
  -var 'private_subnet_ids=["subnet-c","subnet-d"]' \
  -var acm_certificate_arn=arn:aws:acm:ap-south-1:...:certificate/... \
  -var route53_zone_id=Zxxxx \
  -var control_ami_id=ami-control \
  -var node_ami_id=ami-node-golden \
  -var database_url='postgres://user:pass@rds-endpoint:5432/flash?sslmode=require' \
  -var redis_url='redis://elasticache-endpoint:6379/0'
```

Set `SANDBOXES_PER_NODE` from the **measured** conservative density in `/v1/usage`
(don't guess — that's the whole cost discipline). Golden AMIs are built separately
(Packer): bake the binaries + `scripts/install-gvisor.sh` + `docker pull` of every
template image so a new node is warm in seconds, not minutes.

> Not yet `apply`-ed from here — it needs real account values. `terraform validate`
> passes; treat the AMI build + first apply as the live deploy step.
