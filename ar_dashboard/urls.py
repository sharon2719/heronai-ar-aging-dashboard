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

 # Demo mode endpoints
    path('demo/', views.demo_mode_page, name='demo_mode'),
    path('demo/toggle/', views.demo_toggle, name='demo_toggle'),
    path('demo/metrics/', views.demo_metrics, name='demo_metrics'),
    path('demo/new-invoices/', views.demo_new_invoices, name='demo_new_invoices'),
    path('demo/invoice-paid/', views.demo_invoice_paid, name='demo_invoice_paid'),
    path('demo/invoice-aging/', views.demo_invoice_aging, name='demo_invoice_aging'),
    path('demo/major-overdue/', views.demo_major_overdue, name='demo_major_overdue'),
    path('demo/high-risk-alert/', views.demo_high_risk_alert, name='demo_high_risk_alert'),
    path('demo/reset/', views.demo_reset, name='demo_reset'),
]