from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json
from datetime import datetime, timezone

from .models import Customer, Invoice, ARAgingSummary

# ============================================
# MAIN DASHBOARD VIEWS
# ============================================

def dashboard_home(request):
    """Main dashboard landing page - choose between views"""
    return render(request, 'ar_dashboard/dashboard.html')

def table_view(request):
    """Industry-standard AR Aging report in table format"""
    # Get all AR aging summaries with customer info
    summaries = ARAgingSummary.objects.select_related('customer').all()
    
    # Calculate totals
    total_outstanding = sum(s.total_outstanding for s in summaries)
    total_overdue = sum(s.total_overdue for s in summaries)
    overdue_count = sum(s.overdue_invoices for s in summaries)
    
    # Get bucket totals
    bucket_totals = {}
    for summary in summaries:
        for bucket in ['current', 'days_1_30', 'days_31_60', 'days_61_90', 'days_91_120', 'days_120_plus']:
            if bucket not in bucket_totals:
                bucket_totals[bucket] = Decimal('0')
            bucket_totals[bucket] += getattr(summary, bucket, Decimal('0'))
    
    context = {
        'summaries': summaries,
        'total_outstanding': total_outstanding,
        'total_overdue': total_overdue,
        'overdue_count': overdue_count,
        'bucket_totals': bucket_totals,
    }
    
    return render(request, 'ar_dashboard/table_view.html', context)

def widget_dashboard(request):
    """Interactive dashboard with ECharts visualizations"""
    summaries = ARAgingSummary.objects.select_related('customer').all()
    
    context = {
        'summaries': summaries,
    }
    
    return render(request, 'ar_dashboard/widget_dashboard.html', context)

def filtered_dashboard(request):
    """Filtered dashboard view"""
    return render(request, 'ar_dashboard/filtered_dashboard.html')

# ============================================
# API ENDPOINTS - STANDARD DATA
# ============================================

@require_http_methods(["GET"])
def api_aging_distribution(request):
    """API endpoint: Aging distribution for chart"""
    summaries = ARAgingSummary.objects.all()
    
    data = {
        'Current': float(sum(s.current for s in summaries)),
        '1-30': float(sum(s.days_1_30 for s in summaries)),
        '31-60': float(sum(s.days_31_60 for s in summaries)),
        '61-90': float(sum(s.days_61_90 for s in summaries)),
        '91-120': float(sum(s.days_91_120 for s in summaries)),
        '120+': float(sum(s.days_120_plus for s in summaries)),
    }
    
    return JsonResponse({
        'distribution': data,
        'total': sum(data.values())
    })

@require_http_methods(["GET"])
def api_customer_breakdown(request):
    """API endpoint: Top customers by AR amount"""
    summaries = ARAgingSummary.objects.select_related('customer').order_by('-total_outstanding')[:10]
    
    data = []
    for summary in summaries:
        data.append({
            'id': summary.customer.id,
            'customer': summary.customer.name,
            'total_outstanding': float(summary.total_outstanding),
            'overdue': float(summary.total_overdue),
            'invoice_count': summary.total_invoices,
        })
    
    return JsonResponse({'customers': data})

@require_http_methods(["GET"])
def api_invoice_details(request, customer_id):
    """API endpoint: Get all invoices for a customer"""
    try:
        customer = Customer.objects.get(id=customer_id)
    except Customer.DoesNotExist:
        return JsonResponse({'error': 'Customer not found'}, status=404)
    
    invoices = Invoice.objects.filter(customer=customer, amount_due__gt=0).order_by('-due_at')
    
    data = []
    for invoice in invoices:
        data.append({
            'invoice_number': invoice.invoice_number,
            'invoice_date': invoice.invoice_at.isoformat() if invoice.invoice_at else None,
            'due_date': invoice.due_at.isoformat() if invoice.due_at else None,
            'total_amount': float(invoice.total_amount),
            'amount_due': float(invoice.amount_due),
            'days_overdue': invoice.days_overdue,
            'aging_bucket': invoice.aging_bucket,
            'status': invoice.status,
        })
    
    return JsonResponse({
        'customer': customer.name,
        'invoices': data,
        'total_outstanding': sum(float(inv['amount_due']) for inv in data),
    })

@require_http_methods(["GET"])
def api_summary_stats(request):
    """API endpoint: Summary statistics for KPI cards"""
    summaries = ARAgingSummary.objects.all()
    invoices = Invoice.objects.filter(amount_due__gt=0)
    
    total_customers = summaries.count()
    total_ar = sum(s.total_outstanding for s in summaries)
    total_overdue = sum(s.total_overdue for s in summaries)
    total_invoices = invoices.count()
    
    # DSO calculation (simplified)
    avg_days_overdue = invoices.filter(days_overdue__gt=0).values_list('days_overdue', flat=True)
    avg_dso = sum(avg_days_overdue) / len(avg_days_overdue) if avg_days_overdue else 0
    
    # At-risk customers (>90 days overdue)
    at_risk = invoices.filter(days_overdue__gt=90).values('customer__id').distinct().count()
    
    return JsonResponse({
        'total_customers': total_customers,
        'total_ar': float(total_ar),
        'total_overdue': float(total_overdue),
        'overdue_percentage': float((total_overdue / total_ar * 100) if total_ar > 0 else 0),
        'total_invoices': total_invoices,
        'avg_days_overdue': float(avg_dso),
        'at_risk_customers': at_risk,
    })

@require_http_methods(["GET"])
def api_risk_dashboard(request):
    """Risk scoring for all customers"""
    summaries = ARAgingSummary.objects.select_related('customer').all()
    
    customers_by_risk = {
        'critical': [],
        'warning': [],
        'healthy': []
    }
    
    for summary in summaries:
        risk_level = summary.get_risk_level()
        customers_by_risk[risk_level].append({
            'customer_id': summary.customer.id,
            'customer_name': summary.customer.name,
            'risk_score': summary.get_risk_score(),
            'total_outstanding': float(summary.total_outstanding),
            'total_overdue': float(summary.total_overdue),
            'overdue_pct': float((summary.total_overdue / summary.total_outstanding * 100) if summary.total_outstanding > 0 else 0),
            'days_120_plus': float(summary.days_120_plus),
        })
    
    return JsonResponse({
        'critical': sorted(customers_by_risk['critical'], key=lambda x: x['risk_score'], reverse=True),
        'warning': sorted(customers_by_risk['warning'], key=lambda x: x['risk_score'], reverse=True),
        'healthy': customers_by_risk['healthy'],
        'summary': {
            'critical_count': len(customers_by_risk['critical']),
            'warning_count': len(customers_by_risk['warning']),
            'healthy_count': len(customers_by_risk['healthy']),
        }
    })