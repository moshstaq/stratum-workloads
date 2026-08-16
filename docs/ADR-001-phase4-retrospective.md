# ADR-001: Phase 4 Engineering Retrospective

**Date:** August 2026
**Status:** Accepted
**Author:** Moshood Adisa
**Repository:** stratum-workloads

## Context

Phase 4 of Project Stratum deployed two FastAPI microservices
— catalogue and orders — to EKS through the stratum-platform
Golden Path. This was the first workload deployment that
validated the multi-cloud platform end to end. This ADR
captures the significant engineering decisions made during
Phase 4.

## Decision 1 — IRSA trust policy evolves with workload onboarding

### Context

The IRSA trust policy on `role-eks-app-stratum` was created
in Phase 2 with a single subject condition:

system:serviceaccount:stratum:stratum-app

When the catalogue and orders services deployed in Phase 4,
they used different service accounts in a different namespace:
`stratum-catalogue` and `stratum-orders` in
`stratum-workloads`. The IRSA `/config` endpoint returned
`AccessDenied` because the trust policy did not recognise
the new service accounts.

### Decision

The trust policy was updated to allow multiple service
accounts:

```hcl
condition {
  test     = "StringLike"
  variable = "${local.oidc_issuer}:sub"
  values   = [
    "system:serviceaccount:stratum:stratum-app",
    "system:serviceaccount:stratum-workloads:stratum-catalogue",
    "system:serviceaccount:stratum-workloads:stratum-orders"
  ]
}
```

This reflects the collaboration model between platform and
workload teams. The platform provisions the identity mechanism.
The workload defines the consumers. The trust policy is the
contract between them — it must be updated as workloads are
onboarded.

In a production environment this would be automated — a
workload onboarding process that adds service accounts to the
trust policy as part of the Golden Path provisioning. For this
programme the manual update is documented as the current
pattern.

### Consequences

**Positive:**

- Each workload service account has explicit, auditable
  access to the IRSA role
- The trust policy serves as a registry of which workloads
  consume AWS services via pod identity
- The pattern mirrors how federated credentials work on
  Azure — explicit subject claims per consumer

**Negative:**

- Every new workload requires a platform change to the trust
  policy. This is a manual coordination step that adds
  friction to onboarding. Production recommendation: automate
  trust policy updates as part of environment module
  provisioning.

---

## Decision 2 — ECR repositories provisioned by the environment module

### Context

ECR repositories were originally created as platform
infrastructure in `aws-landing-zone/platform/ecr/`. When
Phase 4 workloads needed their own container registries,
the question arose: does the platform create workload
registries, or do workload teams create their own?

### Decision

ECR repository creation was moved into the stratum-platform
environment module. When a developer provisions a workload
environment with four inputs, they automatically receive:

- IAM role
- Security group
- S3 bucket with lifecycle rules
- ECR repository with immutable tags, scan on push, and
  lifecycle policy

The developer does not create, configure, or manage the
container registry. The platform enforces image immutability,
vulnerability scanning, and retention policies automatically.

### Consequences

**Positive:**

- Developers get a container registry from the same four
  inputs that provision everything else — no additional
  configuration step
- Image security policies are enforced by the platform, not
  left to individual teams
- The Golden Path experience is complete — from environment
  provisioning to image push to deployment, no manual
  infrastructure steps

**Negative:**

- Each workload environment creates its own ECR repository.
  Teams that share images across environments would need a
  separate shared registry. This is acceptable for the
  current programme scope.

---

## References

- `services/catalogue/` — Flash sale product catalogue service
- `services/orders/` — Order processing service with IRSA
  validation
- `k8s/` — Kubernetes manifests for both services
- `aws-landing-zone/platform/eks/main.tf` — IRSA trust policy
- `stratum-platform/terraform/aws/environment/` — Environment
  module with ECR
