# stratum-workloads

FastAPI microservices for the Stratum Retail Group flash sale
platform. Two services addressing the core business problem:
unpredictable traffic spikes during flash sales causing revenue
loss and zero visibility into order processing failures.

Deployed to AWS EKS through the stratum-platform Golden Path.
No cloud infrastructure configured in this repository — the
platform provisions everything.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Container-2496ED?logo=docker)](https://docker.com)

---

## Services

### Catalogue Service

Serves product data during flash sales. Read-heavy — handles
thousands of concurrent browse requests during traffic spikes.

| Endpoint         | Method | Purpose                                   |
| ---------------- | ------ | ----------------------------------------- |
| `/health`        | GET    | Health check for load balancer            |
| `/`              | GET    | Service info and region                   |
| `/products`      | GET    | Full product catalogue                    |
| `/products/{id}` | GET    | Single product with flash sale pricing    |
| `/flash-sale`    | GET    | Active flash sale products with discounts |
| `/metrics`       | GET    | Request count and throughput              |

**Flash sale pricing** — products marked `flash_sale: true`
automatically return a `sale_price` calculated from the
`discount_pct`. The catalogue service handles the pricing
logic, not the platform.

### Orders Service

Processes customer orders during flash sales. Write-heavy —
each request creates an order record with validation and
discount application.

| Endpoint       | Method | Purpose                                               |
| -------------- | ------ | ----------------------------------------------------- |
| `/health`      | GET    | Health check for load balancer                        |
| `/`            | GET    | Service info and region                               |
| `/orders`      | POST   | Create a new order                                    |
| `/orders`      | GET    | List all orders                                       |
| `/orders/{id}` | GET    | Retrieve specific order                               |
| `/config`      | GET    | Validate IRSA — retrieves secret from Secrets Manager |
| `/metrics`     | GET    | Request count, order count, throughput                |

**Flash sale discount** — orders with `flash_sale: true`
receive an additional 15% discount on the total. The orders
service handles the business logic.

**IRSA validation** — the `/config` endpoint retrieves
application configuration from AWS Secrets Manager using
pod-level IAM identity. No credentials are stored in the
application, container, or Kubernetes manifest. The AWS SDK
picks up the service account token injected by EKS and
exchanges it for temporary credentials automatically.

---

## Architecture

Customer → ALB → EKS
├── stratum-catalogue (2 replicas)
│ └── /products, /flash-sale
└── stratum-orders (2 replicas)
└── /orders → Secrets Manager (IRSA)

Both services run in the `stratum-workloads` namespace on
EKS. Each has its own Kubernetes service account annotated
with the IRSA role ARN. Traffic enters through the ALB,
routes to ClusterIP services, and reaches pods directly via
VPC-native pod IPs.

---

## Repository Structure

stratum-workloads/
├── services/
│ ├── catalogue/
│ │ ├── main.py ← FastAPI application
│ │ ├── requirements.txt ← Python dependencies
│ │ └── Dockerfile ← Multi-stage build
│ └── orders/
│ ├── main.py
│ ├── requirements.txt
│ └── Dockerfile
├── k8s/
│ ├── namespace.yaml
│ ├── catalogue/
│ │ ├── deployment.yaml
│ │ ├── service.yaml
│ │ └── serviceaccount.yaml
│ └── orders/
│ ├── deployment.yaml
│ ├── service.yaml
│ └── serviceaccount.yaml
├── docs/
│ └── ADR-001-phase4-retrospective.md
└── .gitignore

---

## Local Development

```bash
# Catalogue
cd services/catalogue
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Orders
cd services/orders
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```

---

## Build and Push

```bash
# Authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  688365520256.dkr.ecr.us-east-1.amazonaws.com

# Build and push catalogue
docker build -t stratum-catalogue:v1.0.0 services/catalogue/
docker tag stratum-catalogue:v1.0.0 \
  688365520256.dkr.ecr.us-east-1.amazonaws.com/stratum-platform:catalogue-v1.0.0
docker push \
  688365520256.dkr.ecr.us-east-1.amazonaws.com/stratum-platform:catalogue-v1.0.0

# Build and push orders
docker build -t stratum-orders:v1.0.0 services/orders/
docker tag stratum-orders:v1.0.0 \
  688365520256.dkr.ecr.us-east-1.amazonaws.com/stratum-platform:orders-v1.0.0
docker push \
  688365520256.dkr.ecr.us-east-1.amazonaws.com/stratum-platform:orders-v1.0.0
```

---

## Deploy to EKS

Prerequisites: EKS cluster running, NAT Gateway enabled,
kubeconfig configured.

```bash
aws eks update-kubeconfig --region us-east-1 --name eks-platform

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/catalogue/serviceaccount.yaml
kubectl apply -f k8s/orders/serviceaccount.yaml
kubectl apply -f k8s/catalogue/deployment.yaml
kubectl apply -f k8s/catalogue/service.yaml
kubectl apply -f k8s/orders/deployment.yaml
kubectl apply -f k8s/orders/service.yaml

kubectl get pods -n stratum-workloads
```

---

## Validation

```bash
# Port forward
kubectl port-forward svc/stratum-catalogue \
  -n stratum-workloads 8000:80
kubectl port-forward svc/stratum-orders \
  -n stratum-workloads 8001:80

# Test catalogue
curl http://localhost:8000/health
curl http://localhost:8000/flash-sale

# Test orders
curl -X POST http://localhost:8001/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": "cust-001",
    "items": [
      {"product_id": "flash-001", "quantity": 1, "unit_price": 29.99}
    ],
    "flash_sale": true
  }'

# Validate IRSA
curl http://localhost:8001/config
```

Expected: `/config` returns `"status": "success"` with
secret content from Secrets Manager. No credentials configured
anywhere in the application.

---

## Platform Dependency

This repository contains no cloud infrastructure. Everything
is provisioned by the platform:

| Concern           | Provided By                           |
| ----------------- | ------------------------------------- |
| VPC, subnets      | aws-landing-zone                      |
| EKS cluster       | aws-landing-zone                      |
| IRSA roles        | aws-landing-zone                      |
| ECR repository    | stratum-platform environment module   |
| S3 storage        | stratum-platform environment module   |
| IAM workload role | stratum-platform environment module   |
| CI/CD pipeline    | stratum-platform unified workflow     |
| Secrets           | aws-landing-zone observability module |

---

## Related Repositories

| Repository                                                           | Purpose                                 |
| -------------------------------------------------------------------- | --------------------------------------- |
| [stratum-platform](https://github.com/moshstaq/stratum-platform)     | Multi-cloud internal developer platform |
| [azure-landing-zone](https://github.com/moshstaq/azure-landing-zone) | Azure platform foundation               |
| [aws-landing-zone](https://github.com/moshstaq/aws-landing-zone)     | AWS platform foundation                 |

---

## Author

Moshood Adisa — github.com/moshstaq
