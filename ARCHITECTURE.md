# AR Dashboard - System Architecture & Deployment Guide

## System Architecture Overview

### High-Level Architecture Diagram

``` bash
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│  Web Browser                                                        │
│  ├── Home Dashboard                                                 │
│  ├── Interactive Widget Dashboard                                   │
│  ├── Filtered Dashboard (with exports)                              │
│  └── AR Aging Report (Table View)                                   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP/HTTPS
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  WEB SERVER LAYER                                    │
├──────────────────────────────────────────────────────────────────────┤
│  Nginx (Reverse Proxy & Load Balancer)                               │
│  ├── SSL/TLS Termination                                             │
│  ├── Static File Serving                                             │
│  └── Request Routing                                                 │
└──────────────────────────────┬────────────────────────────────────── ┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│              APPLICATION SERVER LAYER                                │
├──────────────────────────────────────────────────────────────────────┤
│  Gunicorn (WSGI Application Server)                                  │
│  ├── Worker Process 1                                                │
│  ├── Worker Process 2                                                │
│  ├── Worker Process 3                                                │
│  └── Worker Process 4                                                │
└──────────────────────────────┬────────────────────────────────────── ┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  DJANGO LAYER    │  │  ETL ORCHESTRATE │  │  CACHE LAYER     │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ • Views          │  │ • Dagster Jobs   │  │ • Redis          │
│ • Models         │  │ • Data Transform │  │ • Session Store  │
│ • APIs           │  │ • Validation     │  │ • API Cache      │
│ • Forms          │  │ • Logging        │  │                  │
│ • Authentication │  │                  │  │                  │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                        │
├──────────────────────────────────────────────────────────────────────┤
│  PostgreSQL Database                                                 │
│  ├── ar_customer (Customer master data)                              │
│  ├── ar_invoice (Invoice details)                                    │
│  ├── ar_summary (AR aging summaries)                                 │
│  ├── ar_sync_log (ETL execution logs)                                │
│  └── ar_payment_terms (Customer terms)                               │
└──────────────────────────────┬────────────────────────────────────── ┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ EXTERNAL APIS    │  │ SYNC SERVICES    │  │ FILE STORAGE     │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ • QuickBooks     │  │ • Unified.to     │  │ • AWS S3 / GCS   │
│ • OAuth2         │  │ • API Scheduler  │  │ • Export Files   │
│ • Webhooks       │  │ • Error Handling │  │ • Reports        │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

## Component Architecture

### 1. Frontend Layer

**Technology Stack**:

- Django Templates (Jinja2)
- ECharts 5.4+ (Data visualization)
- HTML2PDF (PDF generation)
- CSS3 + Responsive Grid

**Key Components**:

``` bash
templates/ar_dashboard/
├── home.html (Landing page & widget suggestions)
├── widget_dashboard.html (Interactive dashboard)
├── filtered_dashboard.html (Advanced filtering + export)
├── table_view.html (AR aging report)
└── base.html (Template inheritance)
```

**Data Flow**:

``` bash

User Action → JavaScript Event → API Call → Django View → Database Query → JSON Response → ECharts Render
```

### 2. Application Layer (Django)

**Architecture Pattern**: MTV (Model-Template-View)

```python
ar_dashboard/
├── models.py
│   ├── Customer
│   ├── Invoice
│   ├── ARSummary
│   └── SyncLog
├── views.py
│   ├── dashboard_home()
│   ├── table_view()
│   ├── widget_dashboard()
│   ├── filtered_dashboard()
│   ├── api_summary_stats()
│   ├── api_aging_distribution()
│   ├── api_customer_breakdown()
│   ├── api_invoice_details()
│   └── api_dagster_status()
├── urls.py (URL routing)
├── serializers.py (JSON serialization)
├── dagster_utils.py (Pipeline integration)
└── admin.py (Django Admin)
```

**Request Flow**:

``` ini
HTTP Request → URL Router → View Function → ORM Query → Database → Serialization → JSON Response
```

### 3. Data Integration Layer (Unified.to)

**Sync Process**:

```ini
QuickBooks Cloud
    │
    ├── Customers
    ├── Invoices
    ├── Payments
    └── Aging Data
        │
        ▼
Unified.to API
    │
    ├── OAuth2 Authentication
    ├── Data Mapping
    └── Rate Limiting (60 req/min)
        │
        ▼
Dagster ETL Pipeline
    │
    ├── Extract (API calls)
    ├── Transform (Data cleaning & validation)
    ├── Load (Insert into PostgreSQL)
    └── Log (Execution details)
        │
        ▼
PostgreSQL Database
```

### 4. ETL Pipeline (Dagster)

**Job Schedule**:

``` ini
Daily Full Sync at 6:00 AM
    ├── Fetch all customers
    ├── Fetch all invoices (last 90 days)
    ├── Calculate aging buckets
    ├── Update AR summaries
    └── Validate data integrity

Incremental Sync Every 4 Hours (6 AM, 10 AM, 2 PM, 6 PM, 10 PM)
    ├── Fetch recent transactions
    ├── Update invoice status
    ├── Recalculate aging
    └── Sync payments
```

**Assets Definition**:

```python
@asset
def fetch_customers():
    """Extract customers from QuickBooks"""
    
@asset
def fetch_invoices():
    """Extract invoices from QuickBooks"""
    
@asset
def calculate_aging(fetch_invoices):
    """Calculate aging buckets"""
    
@asset
def ar_summary(calculate_aging):
    """Generate AR summary data"""
    
@asset
def sync_to_database(ar_summary):
    """Load data into PostgreSQL"""
```

### 5. Database Schema

```sql
-- Customers Table
CREATE TABLE ar_customer (
    id SERIAL PRIMARY KEY,
    customer_name VARCHAR(255) NOT NULL,
    qb_customer_id VARCHAR(100) UNIQUE,
    email VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Invoices Table
CREATE TABLE ar_invoice (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES ar_customer(id),
    invoice_number VARCHAR(100) UNIQUE,
    invoice_date DATE,
    due_date DATE,
    amount_due DECIMAL(12, 2),
    amount_paid DECIMAL(12, 2) DEFAULT 0,
    status VARCHAR(20), -- OPEN, PAID, OVERDUE
    aging_bucket VARCHAR(20), -- Current, 1-30, 31-60, etc.
    days_overdue INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- AR Summary Table (for fast queries)
CREATE TABLE ar_summary (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES ar_customer(id),
    total_outstanding DECIMAL(12, 2),
    current DECIMAL(12, 2) DEFAULT 0,
    days_1_30 DECIMAL(12, 2) DEFAULT 0,
    days_31_60 DECIMAL(12, 2) DEFAULT 0,
    days_61_90 DECIMAL(12, 2) DEFAULT 0,
    days_91_120 DECIMAL(12, 2) DEFAULT 0,
    days_120_plus DECIMAL(12, 2) DEFAULT 0,
    total_overdue DECIMAL(12, 2) DEFAULT 0,
    overdue_percentage DECIMAL(5, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Sync Log Table
CREATE TABLE ar_sync_log (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50), -- FULL, INCREMENTAL
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    records_processed INTEGER,
    records_failed INTEGER,
    status VARCHAR(20), -- SUCCESS, FAILED, PARTIAL
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_customer_id ON ar_invoice(customer_id);
CREATE INDEX idx_invoice_status ON ar_invoice(status);
CREATE INDEX idx_aging_bucket ON ar_invoice(aging_bucket);
CREATE INDEX idx_due_date ON ar_invoice(due_date);
CREATE INDEX idx_sync_log_date ON ar_sync_log(created_at);
```

## Deployment Architecture

### Development Environment

**Local Setup**:

``` ini
Your Machine
├── Python venv
├── Django Dev Server (port 8000)
├── PostgreSQL (local or Docker)
├── Dagster Dev Server (port 3000)
└── .env (local configuration)
```

**Running Locally**:

```bash
# Terminal 1: Django
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000

# Terminal 2: Dagster
dagster dev -f dagster_project/repository.py

# Terminal 3: PostgreSQL (if Docker)
docker run -d --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15
```

### Production Environment (AWS)

``` bash
┌─────────────────────────────────────────────────────────┐
│                    AWS Architecture                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Route 53 (DNS)                                         │
│  └──→ yourdomain.com                                    │
│       │                                                 │
│       ▼                                                 │
│  CloudFront (CDN)                                       │
│  ├── Static files caching                               │
│  └── DDoS protection                                    │
│       │                                                 │
│       ▼                                                 │
│  Application Load Balancer                              │
│  ├── Port 80 → 443 redirect                             │
│  └── SSL/TLS termination                                │
│       │                                                 │
│       ▼                                                 │
│  Auto Scaling Group (EC2)                               │
│  ├── Instance 1 (app server)                            │
│  ├── Instance 2 (app server)                            │
│  └── Instance 3 (app server)                            │
│       │                                                 │
│  ┌────┴────────────────────────────────┐                │
│  │                                     │                │
│  ▼                                     ▼                │
│ RDS PostgreSQL                    ElastiCache Redis     │
│ ├── Multi-AZ                      ├── Session cache     │
│ ├── Automated backups             ├── API cache         │
│ ├── Read replicas                 └── Rate limiting     │
│ └── 30-day retention              │                     │
│                                   │                     │
│  S3 Bucket (for exports)          │                     │
│  ├── CSV reports                  │                     │
│  └── PDF exports          ◀────── ┘                     │
│                                                         │
│  CloudWatch (Monitoring)                                │
│  ├── Log groups                                         │
│  ├── Metrics & alarms                                   │
│  └── Dashboards                                         │
│                                                         │
│  Secrets Manager                                        │
│  ├── Database credentials                               │
│  ├── API keys                                           │
│  └── OAuth tokens                                       │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Docker Compose Setup (Local Development)

**docker-compose.yml**:

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:15-alpine
    container_name: ar-dashboard-db
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: ar-dashboard-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Django Application
  web:
    build: .
    container_name: ar-dashboard-web
    command: >
      sh -c "python manage.py migrate &&
             python manage.py collectstatic --noinput &&
             gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4"
    volumes:
      - .:/app
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=db
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
      - REDIS_URL=redis://redis:6379/0
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Dagster Webserver
  dagster-webserver:
    image: dagster/dagster:latest
    container_name: ar-dashboard-dagster
    command: dagster-webserver -h 0.0.0.0 -p 3000
    volumes:
      - ./dagster_project:/workspace
    ports:
      - "3000:3000"
    environment:
      - DAGSTER_POSTGRES_HOST=db
      - DAGSTER_POSTGRES_DB=dagster
      - DAGSTER_POSTGRES_USER=${DB_USER}
      - DAGSTER_POSTGRES_PASSWORD=${DB_PASSWORD}
    depends_on:
      - db

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: ar-dashboard-nginx
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_volume:/app/staticfiles:ro
      - media_volume:/app/media:ro
    ports:
      - "80:80"
    depends_on:
      - web

volumes:
  postgres_data:
  static_volume:
  media_volume:
```

### Kubernetes Deployment (Advanced)

**k8s/deployment.yaml**:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ar-dashboard

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-app
  namespace: ar-dashboard
spec:
  replicas: 3
  selector:
    matchLabels:
      app: django-app
  template:
    metadata:
      labels:
        app: django-app
    spec:
      containers:
      - name: django
        image: youraccount/ar-dashboard:latest
        ports:
        - containerPort: 8000
        env:
        - name: DEBUG
          value: "False"
        - name: DB_HOST
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: host
        - name: DB_NAME
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: name
        - name: DB_USER
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: user
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: password
        livenessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: django-service
  namespace: ar-dashboard
spec:
  selector:
    app: django-app
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Monitoring & Observability

### Application Health Checks

Create a health check endpoint in Django:

```python
# views.py
from django.http import JsonResponse
from django.db import connections

def health_check(request):
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        conn = connections['default']
        conn.ensure_connection()
        
        # Check Redis connection (if using)
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        
        return JsonResponse({
            'status': 'healthy',
            'database': 'connected',
            'cache': 'connected',
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=500)
```

### Logging Configuration

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/ar-dashboard/django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
```

### Metrics to Monitor

``` ini
Application Metrics:
├── Request Latency (p50, p95, p99)
├── Error Rate (4xx, 5xx responses)
├── Active Connections
├── Database Query Time
├── Cache Hit Ratio
└── Concurrent Users

Business Metrics:
├── Total AR Outstanding
├── Overdue Percentage
├── Top Overdue Customers
├── Collection Rate
└── Days Sales Outstanding (DSO)

Infrastructure Metrics:
├── CPU Usage
├── Memory Usage
├── Disk Space
├── Network I/O
└── Database Connection Pool
```

### Alerting Rules

```yaml
# AlertManager config
groups:
  - name: application
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        
      - alert: HighLatency
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        
      - alert: DatabaseDown
        expr: pg_up == 0
        for: 1m
        
      - alert: DagsterPipelineFailed
        expr: dagster_pipeline_failures_total > 0
        for: 10m
```

## Scaling Strategy

### Horizontal Scaling

1. **Load Balancer**: Route traffic across multiple app servers
2. **Database Read Replicas**: Distribute read-heavy queries
3. **Caching Layer**: Reduce database load
4. **CDN**: Cache static content globally

### Vertical Scaling

- Increase server resources (CPU, RAM)
- Upgrade database instance class
- Increase worker processes

### Database Optimization

```sql
-- Query optimization
EXPLAIN ANALYZE SELECT * FROM ar_invoice WHERE status = 'OVERDUE';

-- Index maintenance
REINDEX TABLE ar_invoice;
VACUUM ANALYZE ar_invoice;

-- Partitioning (for large datasets)
CREATE TABLE ar_invoice_2024 PARTITION OF ar_invoice
  FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

## Backup & Recovery Strategy

### Automated Backups

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR="/backups/ar-dashboard"
DATE=$(date +%Y%m%d_%H%M%S)

# PostgreSQL backup
pg_dump ar_dashboard | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Compress and upload to S3
aws s3 cp "$BACKUP_DIR/db_$DATE.sql.gz" s3://ar-dashboard-backups/

# Cleanup old backups (keep 30 days)
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +30 -delete
```

### Recovery Procedure

```bash
# Restore from backup
gunzip < backup.sql.gz | psql ar_dashboard

# Verify data integrity
SELECT COUNT(*) FROM ar_customer;
SELECT COUNT(*) FROM ar_invoice;
```

## Cost Optimization

### AWS Cost Breakdown (Estimated Monthly)

``` ini
EC2 Instances (3 x t3.medium): $90
RDS PostgreSQL (db.t3.small): $60
ElastiCache Redis: $20
CloudFront CDN: $10-50 (varies)
S3 Storage: $5-20 (varies)
Data Transfer: $10-30 (varies)
─────────────────────────
Total: ~$195-265/month
```

### Cost Reduction Tips

1. Use reserved instances (30% discount)
2. Implement caching to reduce database load
3. Archive old data to cheaper storage
4. Use auto-scaling to match demand
5. Monitor and clean up unused resources

## Disaster Recovery Plan

### RTO & RPO Targets

- **RTO (Recovery Time Objective)**: < 1 hour
- **RPO (Recovery Point Objective)**: < 15 minutes

### Disaster Scenarios & Recovery

| Scenario | Recovery Time | Steps |
|----------|---------------|-------|
| Database corruption | 30 min | Restore from last backup |
| Application server failure | 5 min | Auto-scaling triggers new instance |
| Region outage | 1-2 hours | Failover to secondary region |
| Complete data loss | 30 min | Restore from encrypted backup in S3 |

## Security Checklist

- [ ] Enable SSL/TLS (HTTPS)
- [ ] Use security headers (HSTS, CSP, X-Frame-Options)
- [ ] Implement rate limiting
- [ ] Enable audit logging
- [ ] Regular security scans
- [ ] Update dependencies monthly
- [ ] Use secrets management (AWS Secrets Manager)
- [ ] Enable MFA for admin access
- [ ] Regular penetration testing
- [ ] GDPR/Data privacy compliance

## Performance Tuning

### Database Query Optimization

```python
# BAD - N+1 queries
customers = Customer.objects.all()
for customer in customers:
    print(customer.invoices.count())  # Separate query per customer

# GOOD - Use select_related
customers = Customer.objects.prefetch_related('invoices')
for customer in customers:
    print(customer.invoices.count())  # Uses prefetched data
```

### Caching Strategy

```python
# Cache API responses
from django.views.decorators.cache import cache_page

@cache_page(60 * 15)  # 15 minutes
def api_summary_stats(request):
    # Expensive query
    return JsonResponse(data)

# Cache model queries
from django.core.cache import cache

def get_aging_distribution():
    cached = cache.get('aging_distribution')
    if cached:
        return cached
    
    data = calculate_expensive_aggregation()
    cache.set('aging_distribution', data, 60 * 30)  # 30 minutes
    return data
```

## Continuous Integration & Deployment (CI/CD)

### GitHub Actions Workflow

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.10
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python manage.py test
      - name: Run linting
        run: flake8 .

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to AWS
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URI
          docker build -t ar-dashboard:latest .
          docker tag ar-dashboard:latest $ECR_URI/ar-dashboard:latest
          docker push $ECR_URI/ar-dashboard:latest
          # Update ECS service
```

---

**Last Updated**: 2025
**Version**: 1.0.0
