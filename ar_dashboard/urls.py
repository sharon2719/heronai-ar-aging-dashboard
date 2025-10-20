from django.urls import path
from ar_dashboard import views

app_name = 'ar_dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('table/', views.table_view, name='table_view'),
    path('dashboard/', views.widget_dashboard, name='widget_dashboard'),
    path('dashboard-filtered/', views.filtered_dashboard, name='filtered_dashboard'),
    
    # API endpoints
    path('api/aging-distribution/', views.api_aging_distribution, name='api_aging_distribution'),
    path('api/customer-breakdown/', views.api_customer_breakdown, name='api_customer_breakdown'),
    path('api/invoice-details/<int:customer_id>/', views.api_invoice_details, name='api_invoice_details'),
    path('api/summary-stats/', views.api_summary_stats, name='api_summary_stats'),
    path('api/risk-dashboard/', views.api_risk_dashboard, name='api_risk_dashboard'),
]