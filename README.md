# Accounts Receivable Dashboard

A comprehensive Django-based analytics platform for managing and visualizing accounts receivable (AR) data with real-time insights, interactive dashboards, and advanced filtering capabilities.

## Table of Contents

- [Features](#features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running Locally](#running-locally)
- [API Endpoints](#api-endpoints)
- [Deployment](#deployment)
- [Dashboard Features](#dashboard-features)
- [Troubleshooting](#troubleshooting)

## Features

- **Real-time AR Analytics**: Live data sync from QuickBooks via Unified.to API
- **Interactive Dashboards**: Multiple dashboard views with customizable widgets
- **Advanced Filtering**: Filter by aging buckets, amount ranges, customer names
- **Data Export**: Export to CSV and PDF formats
- **Pipeline Monitoring**: Real-time Dagster ETL pipeline status tracking
- **Responsive Design**: Works on desktop, tablet, and mobile devices
- **Aging Analysis**: Industry-standard aging report with time bucket breakdown
- **Customer Insights**: Detailed customer-level AR analysis with risk scoring
- **Print-Ready Reports**: Optimized layouts for printing and stakeholder sharing

## System Architecture

``` bash
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Layer                           │
├─────────────────────────────────────────────────────────────┤
│  • Django Templates (HTML/CSS)                              │
│  • ECharts (Data Visualization)                             │
│  • HTML2PDF (Report Generation)                             │
│  • Responsive Bootstrap Grid                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Django Application Layer                       │
├─────────────────────────────────────────────────────────────┤
│  • ar_dashboard (Main App)                                  │
│    ├── views.py (Request Handlers)                          │
│    ├── models.py (Data Models)                              │
│    ├── urls.py (Routing)                                    │
│    ├── serializers.py (JSON API)                            │
│    └── dagster_utils.py (Pipeline Integration)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────┐
│         Data Processing & ETL Layer (Dagster)               │
├──────────────────────┼──────────────────────────────────────┤
│  • Asset Definitions                                        │
│  • Job Orchestration                                        │
│  • Scheduled Runs (Daily 6 AM, 4-Hour Intervals)            │
│  • Data Transformation & Validation                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────┐
│           Data Integration Layer (Unified.to)               │
├──────────────────────┼──────────────────────────────────────┤
│  • QuickBooks Integration                                   │
│  • Unified.to API Connector                                 │
│  • OAuth2 Authentication                                    │
│  • Real-time & Scheduled Sync                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              Database Layer                                 │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL                                                 │
│  ├── ar_summary (Aging buckets by customer)                 │
│  ├── ar_invoice (Individual invoice details)                │
│  ├── ar_customer (Customer master data)                     │
│  └── ar_sync_log (ETL execution logs)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│           External Data Sources                             │
├─────────────────────────────────────────────────────────────┤
│  • QuickBooks Cloud                                         │
│  • Unified.to API                                           │
│  • Dagster Cloud (Optional)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

### Backend

- **Framework**: Django 4.2+
- **Python**: 3.10+
- **Database**: PostgreSQL 12+
- **ETL**: Dagster
- **API Integration**: Unified.to, QuickBooks

### Frontend

- **Templates**: Django Jinja2
- **Charts**: ECharts 5.4+
- **Styling**: CSS3, Tailwind utilities
- **Export**: html2pdf.js

### Infrastructure

- **Server**: Gunicorn + Nginx
- **Container**: Docker
- **Orchestration**: Docker Compose
- **Hosting**: AWS/DigitalOcean/Self-hosted

## Prerequisites

- Python 3.10 or higher
- PostgreSQL 12 or higher
- Docker & Docker Compose (for containerized deployment)
- Git
- Node.js 16+ (optional, for frontend tooling)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/ar-dashboard.git
cd ar-dashboard
```

### 2. Create Python Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables

Create a `.env` file in the project root:

```env
# Django
DEBUG=False
SECRET_KEY=your-secret-key-here-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
ENVIRONMENT=production

# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=awour-db-name
DB_USER=postgres
DB_PASSWORD=secure-password-here
DB_HOST=localhost
DB_PORT=5432

# Unified.to / QuickBooks
UNIFIED_API_KEY=your-unified-api-key
QB_REALM_ID=your-quickbooks-realm-id
QB_CLIENT_ID=your-client-id
QB_CLIENT_SECRET=your-client-secret

# Dagster
DAGSTER_URL=http://localhost:3000
DAGSTER_API_KEY=your-dagster-api-key

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-email-password

# AWS/S3 (Optional)
USE_S3=False
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=
```

### 5. Create PostgreSQL Database

```bash
createdb ar_dashboard
```

### 6. Run Migrations

```bash
python manage.py migrate
```

### 7. Create Superuser

```bash
python manage.py createsuperuser
```

## Configuration

### Settings Configuration

Edit `your_project/settings.py`:

```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'ar_dashboard',
]

# CORS Settings
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
    "https://yourdomain.com",
]

# Database
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE'),
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# Static & Media Files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100
}
```

## Running Locally

### 1. Start PostgreSQL

```bash
# If using Docker
docker run -d --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15

# Or use local installation
brew services start postgresql  # macOS
```

### 2. Start Dagster (in separate terminal)

```bash
dagster dev -f dagster_project/repository.py
# Accessible at http://localhost:3000
```

### 3. Start Django Development Server

```bash
python manage.py runserver 0.0.0.0:8000
```

### 4. Access the Application

- Dashboard: <http://localhost:8000/ar/>
- Admin: <http://localhost:8000/admin/>
- API: <http://localhost:8000/ar/api/>

## API Endpoints

### Summary Statistics

``` json
GET /ar/api/summary-stats/
Response: {
  "total_customers": 8,
  "total_ar": 24566.0,
  "total_overdue": 24566.0,
  "overdue_percentage": 100.0,
  "total_invoices": 29,
  "avg_days_overdue": 993.21,
  "at_risk_customers": 8
}
```

### Aging Distribution

``` json
GET /ar/api/aging-distribution/
Response: {
  "distribution": {
    "Current": 0.0,
    "1-30": 630.0,
    "31-60": 0.0,
    "61-90": 0.0,
    "91-120": 0.0,
    "120+": 23936.0
  },
  "total": 24566.0
}
```

### Customer Breakdown

``` json
GET /ar/api/customer-breakdown/
Response: {
  "customers": [
    {
      "id": 6,
      "customer": "Misael Anderson",
      "total_outstanding": 7210.0,
      "overdue": 7210.0,
      "invoice_count": 1
    }
  ]
}
```

### Invoice Details

``` json
GET /ar/api/invoice-details/<customer_id>/
Response: {
  "invoices": [
    {
      "invoice_number": "INV-001",
      "invoice_date": "2024-01-15",
      "due_date": "2024-02-15",
      "amount_due": 1500.0,
      "days_overdue": 30,
      "status": "OVERDUE",
      "aging_bucket": "31-60"
    }
  ]
}
```

### Dagster Pipeline Status

``` json
GET /ar/api/dagster-status/
Response: {
  "status": "success",
  "message": "Last run: SUCCESS",
  "jobName": "ar_data_pipeline",
  "runs": [...]
}
```

## Deployment

### Docker Deployment

#### 1. Create Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and start server
CMD ["sh", "-c", "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:8000"]
```

#### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ar_dashboard
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  web:
    build: .
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=db
      - DEBUG=False
    depends_on:
      - db
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  dagster:
    image: dagster/dagster-k8s:latest
    ports:
      - "3000:3000"
    environment:
      - POSTGRES_HOST=db
      - DB_PASSWORD=${DB_PASSWORD}
    depends_on:
      - db

volumes:
  postgres_data:
```

#### 3. Build and Deploy

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

### AWS Deployment (EC2 + RDS)

#### 1. Launch EC2 Instance

```bash
# Use Ubuntu 22.04 LTS
# t3.medium or larger recommended
# Security Group: Allow ports 80, 443, 8000
```

#### 2. Install Dependencies on EC2

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.10 python3.10-venv postgresql-client git nginx

# Clone repository
git clone https://github.com/yourusername/ar-dashboard.git
cd ar-dashboard

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
pip install gunicorn
```

#### 3. Configure Nginx

Create `/etc/nginx/sites-available/ar-dashboard`:

```nginx
upstream django {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static/ {
        alias /home/ubuntu/ar-dashboard/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/ar-dashboard/media/;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/ar-dashboard /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

#### 4. Create Systemd Service

Create `/etc/systemd/system/ar-dashboard.service`:

```ini
[Unit]
Description=AR Dashboard Gunicorn Service
After=network.target

[Service]
Type=notify
User=ubuntu
WorkingDirectory=/home/ubuntu/ar-dashboard
ExecStart=/home/ubuntu/ar-dashboard/venv/bin/gunicorn \
    --workers 4 \
    --bind 127.0.0.1:8000 \
    config.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl start ar-dashboard
sudo systemctl enable ar-dashboard
```

#### 5. Set Up SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d yourdomain.com
```

#### 6. RDS Database

Create PostgreSQL RDS instance:

- Engine: PostgreSQL 15
- Instance class: db.t3.small or larger
- Multi-AZ: Yes (for production)
- Backup retention: 30 days

Update `.env` with RDS endpoint.

### DigitalOcean App Platform

1. Connect your GitHub repository
2. Create new app from repository
3. Configure environment variables in dashboard
4. Add PostgreSQL managed database
5. Deploy

## Dashboard Features

### 1. Home Dashboard

- Welcome page with suggested workflows
- Quick-start cards for different views
- Feature overview
- Navigation to all tools

### 2. Interactive Widget Dashboard

- Drag-and-drop widgets (customizable layout)
- KPI summary cards
- Aging distribution pie chart
- Top customers bar chart
- Payment velocity analysis
- Customer health scores
- DSO trends
- Collection effectiveness index
- Cash flow forecasts

### 3. Filtered Dashboard

- Advanced filtering controls
- Real-time data filtering
- Export functionality (CSV, PDF)
- Pipeline status monitoring
- Active filter badges

### 4. Table View (AR Aging Report)

- Industry-standard aging report
- Detailed customer breakdown
- Time bucket analysis
- Print-optimized layout
- Drill-down capabilities

## Monitoring & Maintenance

### Database Backups

```bash
# Daily backup at 2 AM
0 2 * * * pg_dump ar_dashboard | gzip > /backups/ar_dashboard_$(date +\%Y\%m\%d).sql.gz
```

### Log Monitoring

```bash
# View Django logs
tail -f /var/log/ar-dashboard/django.log

# View Gunicorn logs
journalctl -u ar-dashboard -f
```

### Health Checks

```bash
# Add to crontab for health monitoring
*/5 * * * * curl -f http://localhost:8000/health/ || systemctl restart ar-dashboard
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Error

``` bash
Error: could not translate host name "db" to address
```

**Solution**: Ensure PostgreSQL is running and `.env` credentials are correct.

#### 2. Static Files Not Loading

```bash
python manage.py collectstatic --noinput
```

#### 3. Dagster Connection Error

Ensure Dagster is running on port 3000:

```bash
dagster dev -f dagster_project/repository.py
```

#### 4. API Returning 404

Check that URLs are properly configured and views are imported.

#### 5. CSV/PDF Export Not Working

Ensure `html2pdf.js` is loaded from CDN and permissions are set correctly.

## Performance Optimization

- **Database Indexing**: Add indexes to frequently queried columns
- **Caching**: Implement Redis caching for summary statistics
- **Query Optimization**: Use `select_related()` and `prefetch_related()`
- **Pagination**: Limit API responses to reasonable page sizes
- **CDN**: Serve static files from CDN in production

## Security Best Practices

- Never commit `.env` files
- Use strong SECRET_KEY (generate with `django.core.management.utils.get_random_secret_key()`)
- Enable HTTPS in production
- Set `DEBUG=False` in production
- Use environment variables for all sensitive data
- Implement rate limiting on APIs
- Regular security updates for dependencies

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Support

For issues and questions:

- Open an issue on GitHub
- Check existing documentation

## Changelog

### Version 1.0.0

- Initial release
- Core dashboard functionality
- Interactive widgets
- Filtered dashboard with export
- Dagster pipeline integration
- Multi-view reports
# heronai-ar-aging-dashboard
