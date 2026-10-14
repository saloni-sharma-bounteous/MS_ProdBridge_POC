# Common AWS stack patterns

Use as a starting point for the architecture step. For each, **verify details with the AWS Knowledge MCP** (best practices, quotas, regional availability) and the Terraform MCP (arguments, module versions) before writing code. These notes are guidance, not copy-paste code.

## Contents
1. Static site
2. Serverless API
3. Container service
4. Web app with database
5. Event-driven pipeline
6. Questions to ask the Knowledge MCP

## 1. Static site (S3 + CloudFront)
- Private S3 bucket, CloudFront with Origin Access Control, ACM certificate in `us-east-1` for the CDN, Route 53 alias, security headers policy, versioned bucket, logging.
- Watch: certificate region, cache invalidation in the deploy script.

## 2. Serverless API (API Gateway + Lambda + DynamoDB)
- HTTP API (cheaper) unless REST features are needed, Lambda with least-privilege role, DynamoDB on-demand with point-in-time recovery, CloudWatch log retention, X-Ray optional, DLQ for async invokes.
- Watch: Lambda packaging in the deploy script, reserved concurrency, throttling, API auth.

## 3. Container service (ECS Fargate + ALB)
- VPC with public (ALB) and private (tasks) subnets, ECR with scan on push, task execution role vs task role, ALB with HTTPS and redirect, autoscaling, `awslogs` driver, secrets from Secrets Manager.
- Watch: NAT cost, health check path, deployment circuit breaker, image tag immutability.

## 4. Web app with database
- Pattern 3 plus RDS or Aurora in private subnets, subnet group, encryption, backups, Multi-AZ for prod, deletion protection for prod, credentials in Secrets Manager with rotation, security group that only allows the app tier.

## 5. Event-driven pipeline (S3/SQS/SNS/EventBridge + Lambda or Step Functions)
- Queues with DLQs and redrive, encryption, idempotent consumers, EventBridge rules with input transformers, Step Functions for orchestration with retries and catch.

## 6. Questions to ask the Knowledge MCP
- "Is `<service>` available in `<region>`?"
- "What are the default quotas and hard limits for `<service>`?"
- "What are the security best practices for `<service>`?"
- "What is the recommended way to `<do X>` according to the Well-Architected Framework?"
- "How does `<service A>` integrate with `<service B>` and what permissions are needed?"
Record the answer and the source page in `docs/architecture.md` so decisions are traceable.
