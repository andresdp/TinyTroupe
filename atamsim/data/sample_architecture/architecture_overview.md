# ShopFlow E-Commerce Platform — Architecture Overview

## System Purpose

ShopFlow is a cloud-native e-commerce platform supporting online retail for
mid-to-large merchants. It handles product catalogs, shopping cart, checkout,
payment processing, order fulfillment, and customer account management.

## High-Level Architecture

The system follows a microservices architecture deployed on Kubernetes.

### Core Services

1. **API Gateway** — Single entry point; handles routing, rate limiting,
   and authentication via JWT tokens.
2. **Product Service** — Manages the product catalog. Reads from a
   PostgreSQL primary with read replicas.
3. **Cart Service** — Stateless service using Redis for session-based carts.
4. **Order Service** — Orchestrates checkout; publishes events to Kafka.
5. **Payment Service** — Integrates with third-party payment providers
   (Stripe, PayPal) via their REST APIs.
6. **User Service** — Manages accounts, profiles, and authentication.
7. **Notification Service** — Consumes events from Kafka and sends emails/SMS.

### Data Stores

- **PostgreSQL** — Primary transactional database (orders, users, products).
  Read replicas for product catalog queries.
- **Redis** — Session carts and caching layer.
- **Elasticsearch** — Product search and faceted filtering.
- **Kafka** — Event bus for async communication between services.
- **S3** — Product images and static assets.

### Infrastructure

- **Kubernetes (EKS)** — Container orchestration.
- **Istio Service Mesh** — mTLS between services, traffic management.
- **Application Load Balancer** — Public-facing ingress.
- **CloudWatch + Prometheus/Grafana** — Monitoring and alerting.

## Architectural Patterns

- **API Gateway** pattern for centralized entry point.
- **CQRS** for product catalog (read replicas separate from writes).
- **Event Sourcing** for order lifecycle (events stored in Kafka).
- **Saga pattern** for distributed transactions across checkout.
- **Circuit Breaker** for third-party integrations (payment providers).
- **Sidecar** pattern via Istio for observability and security.

## Technology Stack

- **Backend:** Java 17 / Spring Boot 3.x
- **Frontend:** React 18 (Next.js for SSR)
- **Mobile:** React Native
- **Database:** PostgreSQL 15
- **Cache:** Redis 7
- **Search:** Elasticsearch 8
- **Message Broker:** Apache Kafka
- **Containerization:** Docker + Kubernetes (EKS)
- **CI/CD:** GitHub Actions → ArgoCD (GitOps)

## Key Quality Concerns

- **Performance:** Product search must return results in < 200ms p95.
- **Availability:** Checkout flow must be 99.99% available during peak season.
- **Scalability:** Must handle 10x traffic during Black Friday.
- **Security:** PCI-DSS compliance for payment handling.
- **Modifiability:** New payment providers must be addable within 1 sprint.