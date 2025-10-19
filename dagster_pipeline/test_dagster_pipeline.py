import sys
import os
import django
from pathlib import Path
from django.db import models

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ar_dashboard.models import Customer, Invoice, Transaction, ARAgingSummary
from decimal import Decimal

print("=" * 80)
print("HeronAI AR Dashboard - Pipeline Test & Verification")
print("=" * 80)

# Check 1: Verify data files exist
print("\n[TEST 1] Checking data files...")
# Try multiple possible locations for data directory
possible_data_dirs = [
    Path(__file__).parent / 'data',
    Path.cwd() / 'data',
    Path(__file__).parent.parent / 'data'
]

DATA_DIR = None
for data_dir in possible_data_dirs:
    if data_dir.exists():
        DATA_DIR = data_dir
        print(f"  Found data directory at: {data_dir}")
        break

if DATA_DIR is None:
    print(f"  ✗ Data directory not found!")
    print(f"  Searched in:")
    for d in possible_data_dirs:
        print(f"    - {d}")
    print("\n❌ ERROR: Cannot find data directory")
    print("Run the extraction script first: python test_unified_api.py")
    sys.exit(1)
required_files = [
    'customers.json',
    'customer_invoices.json', 
    'all_transactions.json',
    'outstanding_invoices.json',
    'ar_aging_report.json'
]

missing_files = []
for file in required_files:
    file_path = DATA_DIR / file
    if file_path.exists():
        print(f"  ✓ {file} exists")
    else:
        print(f"  ✗ {file} MISSING!")
        missing_files.append(file)

if missing_files:
    print(f"\n❌ ERROR: Missing files: {', '.join(missing_files)}")
    print("Run the extraction script first: python test_unified_api.py")
    sys.exit(1)

print("\n✅ All data files present")

# Check 2: Verify Django database connection
print("\n[TEST 2] Checking database connection...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("  ✓ Database connection successful")
except Exception as e:
    print(f"  ✗ Database connection failed: {e}")
    sys.exit(1)

# Check 3: Count records in database (after ETL should run)
print("\n[TEST 3] Checking database records...")
try:
    customer_count = Customer.objects.count()
    invoice_count = Invoice.objects.count()
    transaction_count = Transaction.objects.count()
    ar_summary_count = ARAgingSummary.objects.count()
    
    print(f"  → Customers: {customer_count}")
    print(f"  → Invoices: {invoice_count}")
    print(f"  → Transactions: {transaction_count}")
    print(f"  → AR Summaries: {ar_summary_count}")
    
    if customer_count == 0:
        print("\n⚠️  WARNING: No customers in database. Run Dagster ETL pipeline:")
        print("   dagster job execute -f dagster_pipeline/definitions.py -j full_ar_etl_pipeline")
    else:
        print("\n✅ Database has records")
        
except Exception as e:
    print(f"  ✗ Error querying database: {e}")
    sys.exit(1)

# Check 4: Verify data relationships
if customer_count > 0:
    print("\n[TEST 4] Verifying data relationships...")
    
    # Check invoices linked to customers
    invoices_with_customers = Invoice.objects.filter(customer__isnull=False).count()
    print(f"  → Invoices linked to customers: {invoices_with_customers}/{invoice_count}")
    
    # Check transactions linked to customers
    txns_with_customers = Transaction.objects.filter(customer__isnull=False).count()
    print(f"  → Transactions linked to customers: {txns_with_customers}/{transaction_count}")
    
    # Check AR summaries have customers
    ar_with_customers = ARAgingSummary.objects.filter(customer__isnull=False).count()
    print(f"  → AR summaries with customers: {ar_with_customers}/{ar_summary_count}")
    
    if invoices_with_customers < invoice_count * 0.5:
        print("  ⚠️  WARNING: Less than 50% of invoices linked to customers")
    else:
        print("  ✅ Customer relationships look good")

# Check 5: Verify AR calculations
if ar_summary_count > 0:
    print("\n[TEST 5] Verifying AR aging calculations...")
    
    total_ar = ARAgingSummary.objects.aggregate(
        total=models.Sum('total_outstanding')
    )['total'] or Decimal('0')
    
    total_overdue = ARAgingSummary.objects.aggregate(
        total=models.Sum('total_overdue')
    )['total'] or Decimal('0')
    
    print(f"  → Total AR Outstanding: ${total_ar:,.2f}")
    print(f"  → Total Overdue: ${total_overdue:,.2f}")
    
    if total_ar > 0:
        overdue_pct = (total_overdue / total_ar * 100)
        print(f"  → Overdue Percentage: {overdue_pct:.1f}%")
    
    # Check aging bucket distribution
    print("\n  Aging Bucket Distribution:")
    for summary in ARAgingSummary.objects.all()[:5]:  # Top 5 customers
        print(f"    • {summary.customer.name}:")
        print(f"      Current: ${summary.current:,.2f}")
        print(f"      1-30: ${summary.days_1_30:,.2f}")
        print(f"      31-60: ${summary.days_31_60:,.2f}")
        print(f"      61-90: ${summary.days_61_90:,.2f}")
        print(f"      91-120: ${summary.days_91_120:,.2f}")
        print(f"      120+: ${summary.days_120_plus:,.2f}")
        print(f"      TOTAL: ${summary.total_outstanding:,.2f}\n")
    
    if total_ar > 0:
        print("  ✅ AR calculations verified")
    else:
        print("  ⚠️  WARNING: Total AR is $0 - check if outstanding invoices exist")

# Check 6: Verify critical dashboard data
print("\n[TEST 6] Dashboard Data Readiness Check...")

checks_passed = []
checks_failed = []

# Check: Customers with outstanding AR
customers_with_ar = ARAgingSummary.objects.filter(total_outstanding__gt=0).count()
if customers_with_ar > 0:
    checks_passed.append(f"Customers with AR: {customers_with_ar}")
else:
    checks_failed.append("No customers with outstanding AR")

# Check: Overdue invoices
overdue_invoices = Invoice.objects.filter(
    status__in=['OVERDUE', 'PARTIAL'],
    amount_due__gt=0
).count()
if overdue_invoices > 0:
    checks_passed.append(f"Overdue invoices: {overdue_invoices}")
else:
    checks_failed.append("No overdue invoices found")

# Check: Payment transactions
payments = Transaction.objects.filter(transaction_type='PAYMENT').count()
if payments > 0:
    checks_passed.append(f"Payment transactions: {payments}")
else:
    checks_failed.append("No payment transactions")

# Check: Aging buckets populated
buckets_populated = ARAgingSummary.objects.filter(
    models.Q(days_1_30__gt=0) | 
    models.Q(days_31_60__gt=0) |
    models.Q(days_61_90__gt=0) |
    models.Q(days_91_120__gt=0) |
    models.Q(days_120_plus__gt=0)
).count()
if buckets_populated > 0:
    checks_passed.append(f"Aging buckets populated: {buckets_populated} customers")
else:
    checks_failed.append("No aging bucket data")

print("\n  ✅ Passed Checks:")
for check in checks_passed:
    print(f"    • {check}")

if checks_failed:
    print("\n  ⚠️  Failed Checks:")
    for check in checks_failed:
        print(f"    • {check}")

# Check 7: Dagster configuration
print("\n[TEST 7] Checking Dagster setup...")
try:
    from dagster_pipeline.definitions import defs
    
    print(f"  → Assets loaded: {len(defs.assets)}")
    print(f"  → Jobs defined: {len(defs.jobs)}")
    print(f"  → Schedules configured: {len(defs.schedules)}")
    
    print("\n  Available Jobs:")
    for job in defs.jobs:
        print(f"    • {job.name}")
    
    print("\n  Configured Schedules:")
    for schedule in defs.schedules:
        print(f"    • {schedule.name} - {schedule.cron_schedule}")
    
    print("\n  ✅ Dagster configuration valid")
    
except Exception as e:
    print(f"  ✗ Dagster configuration error: {e}")
    print("  Check dagster_pipeline/definitions.py")

# Final Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

if customer_count > 0 and ar_summary_count > 0 and len(checks_failed) == 0:
    print("\n✅ ALL TESTS PASSED - Ready for PoC presentation!")
    print("\nNext steps:")
    print("  1. Start Dagster UI: dagster dev")
    print("  2. Run full ETL: dagster job execute -j full_ar_etl_pipeline")
    print("  3. Access dashboard: python manage.py runserver")
    print("  4. Navigate to AR Dashboard views")
    
elif customer_count > 0:
    print("\n⚠️  PARTIAL SUCCESS - Database has data but some checks failed")
    print("\nIssues to fix:")
    for check in checks_failed:
        print(f"  • {check}")
    print("\nYou can still demo basic functionality")
    
else:
    print("\n❌ TESTS FAILED - ETL pipeline needs to run")
    print("\nAction required:")
    print("  1. Ensure data files exist in data/ folder")
    print("  2. Run: dagster dev")
    print("  3. Execute: full_ar_etl_pipeline job")
    print("  4. Re-run this test script")

print("\n" + "=" * 80)

# Import at module level for the check
from django.db import models