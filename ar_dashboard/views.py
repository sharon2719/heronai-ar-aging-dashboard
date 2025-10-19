from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json
from datetime import datetime, timezone

from .models import Customer, Invoice, ARAgingSummary

# ============================================
# DEMO MODE STATE MANAGEMENT
# ============================================
# Store demo state in memory (or use cache/session in production)
demo_state = {
    'baseline_ar': Decimal('2500000'),
    'baseline_overdue_pct': 35,
    'baseline_customers': 45,
    'baseline_at_risk': 12,
    'invoices_added': 0,
    'invoices_paid': 0,
    'overdue_amount': Decimal('875000'),
    'current_multiplier': 1.0,
    'demo_mode_enabled': False,  # Toggle for demo mode
}

# ============================================
# MAIN DASHBOARD VIEWS
# ============================================

def dashboard_home(request):
    """Main dashboard landing page - choose between views"""
    return render(request, 'ar_dashboard/dashboard.html')

def table_view(request):
    """Industry-standard AR Aging report in table format"""
    # Check if demo mode is enabled
    if demo_state.get('demo_mode_enabled', False):
        # Return demo data
        summaries = ARAgingSummary.objects.select_related('customer').all()
        metrics = get_updated_metrics()
        
        context = {
            'summaries': summaries,
            'total_outstanding': metrics['total_ar'],
            'total_overdue': metrics['total_overdue'],
            'overdue_count': metrics['total_invoices'],
            'bucket_totals': get_demo_bucket_totals(),
            'demo_mode': True,
        }
    else:
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
            'demo_mode': False,
        }
    
    return render(request, 'ar_dashboard/table_view.html', context)

def widget_dashboard(request):
    """Interactive dashboard with ECharts visualizations"""
    summaries = ARAgingSummary.objects.select_related('customer').all()
    
    context = {
        'summaries': summaries,
        'demo_mode': demo_state.get('demo_mode_enabled', False),
    }
    
    return render(request, 'ar_dashboard/widget_dashboard.html', context)

# ============================================
# API ENDPOINTS - STANDARD DATA
# ============================================

@require_http_methods(["GET"])
def api_aging_distribution(request):
    """API endpoint: Aging distribution for chart"""
    if demo_state.get('demo_mode_enabled', False):
        # Return demo data
        return JsonResponse({
            'distribution': get_demo_bucket_totals(),
            'total': float(demo_state['baseline_ar'])
        })
    
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
    if demo_state.get('demo_mode_enabled', False):
        # Return demo metrics
        return JsonResponse(get_updated_metrics())
    
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
    
# ============================================
# DEMO MODE VIEWS & API ENDPOINTS
# ============================================

def demo_mode_page(request):
    """Render demo control panel page"""
    return render(request, 'ar_dashboard/demo_mode.html', {
        'current_state': demo_state
    })

@require_http_methods(["POST"])
def demo_toggle(request):
    """Toggle demo mode on/off"""
    demo_state['demo_mode_enabled'] = not demo_state.get('demo_mode_enabled', False)
    
    return JsonResponse({
        'status': 'success',
        'demo_mode_enabled': demo_state['demo_mode_enabled'],
        'message': f"Demo mode {'enabled' if demo_state['demo_mode_enabled'] else 'disabled'}"
    })

@require_http_methods(["POST"])
def demo_new_invoices(request):
    """Simulate new invoices arriving"""
    data = json.loads(request.body)
    count = data.get('count', 1)
    amount_per_invoice = 30000
    
    demo_state['invoices_added'] += count
    total_amount = count * amount_per_invoice
    
    # Update baseline AR
    demo_state['baseline_ar'] += Decimal(total_amount)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{count} invoice(s) received totaling ${total_amount/1000:.0f}K',
        'metrics': get_updated_metrics(),
        'invoices_added': demo_state['invoices_added']
    })

@require_http_methods(["POST"])
def demo_invoice_paid(request):
    """Simulate invoice payments"""
    data = json.loads(request.body)
    count = data.get('count', 1)
    amount_per_invoice = 40000
    
    demo_state['invoices_paid'] += count
    total_amount = count * amount_per_invoice
    
    # Update baseline AR (decrease)
    demo_state['baseline_ar'] -= Decimal(total_amount)
    if demo_state['baseline_ar'] < 0:
        demo_state['baseline_ar'] = Decimal('100000')
    
    # Update overdue amount (payments reduce overdue)
    demo_state['overdue_amount'] -= Decimal(total_amount * 0.6)
    if demo_state['overdue_amount'] < 0:
        demo_state['overdue_amount'] = Decimal('50000')
    
    # Improve overdue percentage
    demo_state['baseline_overdue_pct'] = max(10, demo_state['baseline_overdue_pct'] - 2)
    
    return JsonResponse({
        'status': 'success',
        'message': f'{count} invoice(s) paid totaling ${total_amount/1000:.0f}K',
        'metrics': get_updated_metrics(),
        'invoices_paid': demo_state['invoices_paid']
    })

@require_http_methods(["POST"])
def demo_invoice_aging(request):
    """Simulate invoice aging (moving to older bucket)"""
    # Move from 31-60 to 61-90 days
    demo_state['overdue_amount'] += Decimal('45000')
    demo_state['baseline_overdue_pct'] = min(100, demo_state['baseline_overdue_pct'] + 5)
    
    return JsonResponse({
        'status': 'success',
        'message': 'Invoice aged from 31-60 to 61-90 days. Overdue amount: +$45K',
        'metrics': get_updated_metrics(),
        'alert': True
    })

@require_http_methods(["POST"])
def demo_major_overdue(request):
    """Simulate major customer going overdue 90+ days"""
    # Add a significant overdue amount
    demo_state['overdue_amount'] += Decimal('250000')
    demo_state['baseline_overdue_pct'] = min(100, demo_state['baseline_overdue_pct'] + 8)
    demo_state['baseline_at_risk'] += 1
    
    return JsonResponse({
        'status': 'success',
        'message': 'Major customer "Acme Corp" moved to 91-120 days ($250K). Health score dropped.',
        'metrics': get_updated_metrics(),
        'alert': True,
        'severity': 'high'
    })

@require_http_methods(["POST"])
def demo_high_risk_alert(request):
    """Simulate high risk situation"""
    demo_state['overdue_amount'] += Decimal('520000')
    demo_state['baseline_overdue_pct'] = min(100, demo_state['baseline_overdue_pct'] + 12)
    demo_state['baseline_at_risk'] += 3
    
    return JsonResponse({
        'status': 'success',
        'message': 'High Risk Alert: 3 customers over 120 days. Total at-risk AR: $520K',
        'metrics': get_updated_metrics(),
        'alert': True,
        'severity': 'critical'
    })

@require_http_methods(["POST"])
def demo_reset(request):
    """Reset demo to baseline state"""
    global demo_state
    demo_mode_enabled = demo_state.get('demo_mode_enabled', False)
    
    demo_state = {
        'baseline_ar': Decimal('2500000'),
        'baseline_overdue_pct': 35,
        'baseline_customers': 45,
        'baseline_at_risk': 12,
        'invoices_added': 0,
        'invoices_paid': 0,
        'overdue_amount': Decimal('875000'),
        'current_multiplier': 1.0,
        'demo_mode_enabled': demo_mode_enabled,  # Preserve demo mode state
    }
    
    return JsonResponse({
        'status': 'success',
        'message': 'Demo reset to baseline metrics',
        'metrics': get_baseline_metrics()
    })

@require_http_methods(["GET"])
def demo_metrics(request):
    """Get current demo metrics (called by dashboard)"""
    return JsonResponse({
        'metrics': get_updated_metrics(),
        'state': {
            'invoices_added': demo_state['invoices_added'],
            'invoices_paid': demo_state['invoices_paid'],
            'demo_mode_enabled': demo_state.get('demo_mode_enabled', False),
        }
    })

# ============================================
# DEMO MODE HELPER FUNCTIONS
# ============================================

def get_baseline_metrics():
    """Return baseline AR metrics"""
    return {
        'total_ar': float(demo_state['baseline_ar']),
        'overdue_percentage': demo_state['baseline_overdue_pct'],
        'total_customers': demo_state['baseline_customers'],
        'at_risk_customers': demo_state['baseline_at_risk'],
        'total_overdue': float(demo_state['overdue_amount']),
        'avg_days_overdue': 45,
        'total_invoices': 87,
        'dso': 45,
        'cei': 72
    }

def get_updated_metrics():
    """Calculate updated metrics based on demo state"""
    total_ar = demo_state['baseline_ar']
    overdue_pct = min(demo_state['baseline_overdue_pct'], 100)
    total_overdue = demo_state['overdue_amount']
    
    # Calculate derived metrics
    dso = int(45 - (demo_state['invoices_paid'] * 1.5))  # DSO improves with payments
    dso = max(dso, 30)
    
    # CEI improves with payments
    cei = min(int(72 + (demo_state['invoices_paid'] * 2)), 95)
    
    # Customer health affects at-risk count
    at_risk = max(demo_state['baseline_at_risk'], 0)
    
    return {
        'total_customers': demo_state['baseline_customers'],
        'total_ar': float(total_ar),
        'total_overdue': float(total_overdue),
        'overdue_percentage': float(overdue_pct),
        'total_invoices': 87 + demo_state['invoices_added'],
        'avg_days_overdue': int(45 + (demo_state['invoices_added'] * 0.8) - (demo_state['invoices_paid'] * 1.2)),
        'at_risk_customers': at_risk,
        'dso': dso,
        'cei': cei
    }

def get_demo_bucket_totals():
    """Get aging bucket totals for demo mode"""
    total_ar = float(demo_state['baseline_ar'])
    
    # Distribute AR across buckets with realistic percentages
    return {
        'Current': total_ar * 0.40,
        '1-30': total_ar * 0.20,
        '31-60': total_ar * 0.15,
        '61-90': total_ar * 0.10,
        '91-120': total_ar * 0.08,
        '120+': total_ar * 0.07,
    }

def filtered_dashboard(request):
        return render(request, 'ar_dashboard/filtered_dashboard.html')
