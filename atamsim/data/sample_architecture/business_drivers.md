# ShopFlow E-Commerce Platform — Business Drivers

## Business Context

ShopFlow is expanding from a single-region deployment to multi-region to
support international growth. The platform currently serves 500K monthly
active users and processes approximately 50K orders per day.

## Key Business Goals

1. **International Expansion** — Launch in 3 new regions (EU, UK, LATAM)
   within 12 months. Requires multi-region data residency compliance.
2. **Peak Season Readiness** — Black Friday traffic is expected to reach
   500K concurrent users (10x normal). Downtime during peak directly costs
   ~$200K/hour in lost revenue.
3. **Mobile-First Strategy** — 70% of traffic now comes from mobile. The
   mobile experience must be sub-second for core flows.
4. **Payment Flexibility** — Merchants are requesting support for regional
   payment methods (PIX in Brazil, SEPA in EU) in addition to existing
   Stripe/PayPal integration.
5. **Cost Optimization** — Cloud spend has grown 40% YoY. The business
   wants to reduce per-transaction infrastructure cost by 25%.

## Constraints

- **Regulatory:** GDPR compliance for EU users; PCI-DSS for payment data.
- **Budget:** Infrastructure budget capped at $2M/year.
- **Timeline:** Peak season (November) is a hard deadline — no major
  changes permitted between October and January.
- **Team:** 4 squads of 6-8 engineers each.

## Success Metrics

- 99.99% checkout availability during peak hours.
- < 200ms p95 latency for product search.
- < 500ms p95 latency for checkout initiation.
- Support for 5+ payment providers by end of year.
- 25% reduction in per-transaction infrastructure cost.