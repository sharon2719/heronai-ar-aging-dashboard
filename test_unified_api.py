import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

load_dotenv()

API_KEY = os.getenv('UNIFIED_API_KEY')
CONNECTION_ID = os.getenv('UNIFIED_CONNECTION_ID')

BASE_URL = f"https://api.unified.to/accounting/{CONNECTION_ID}"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

print("=" * 90)
print("HeronAI AR Aging Dashboard - QuickBooks Data Extraction via Unified.to")
print("=" * 90)
print("Extracting: Customers, Invoices, Payments, Refunds & AR Metrics")
print("=" * 90)

# Helper function to safely get numeric values (handles cents to dollars conversion)
def get_amount(data, field):
    """Safely extract numeric amount from various formats"""
    value = data.get(field, 0)
    if value is None:
        return 0
    try:
        # Unified.to might return amounts in cents, check if conversion needed
        amount = float(value)
        # If amount seems too large (in cents), divide by 100
        # This is a heuristic - you may need to adjust based on actual data
        return amount
    except (ValueError, TypeError):
        return 0

def parse_date(date_str):
    """Parse date string into datetime object"""
    if not date_str:
        return None
    try:
        for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%SZ']:
            try:
                return datetime.strptime(date_str.split('Z')[0].split('+')[0], fmt.replace('Z', ''))
            except:
                continue
        return None
    except:
        return None

# ============================================================================
# STEP 1: Fetch ALL Contacts (Customers & Suppliers)
# ============================================================================
print("\n[STEP 1] Fetching Contacts from QuickBooks...")
try:
    response = requests.get(f"{BASE_URL}/contact", headers=headers)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        all_contacts = response.json()
        print(f"✓ Total contacts retrieved: {len(all_contacts)}")
        
        # Separate customers from suppliers/vendors
        customers = []
        suppliers = []
        
        for contact in all_contacts:
            # Extract email and phone from nested arrays
            emails = contact.get('emails', [])
            phones = contact.get('telephones', []) or contact.get('phones', [])
            
            primary_email = emails[0].get('email') if emails and isinstance(emails[0], dict) else None
            primary_phone = phones[0].get('number') if phones and isinstance(phones[0], dict) else None
            
            # Enhanced contact data for Django models
            enhanced_contact = {
                'external_id': contact.get('id'),
                'name': contact.get('name', 'Unknown'),
                'primary_email': primary_email,
                'primary_phone': primary_phone,
                'is_supplier': contact.get('is_supplier', False),
                'external_created_at': contact.get('created_at'),
                'external_updated_at': contact.get('updated_at'),
                'raw_data': contact
            }
            
            if contact.get('is_supplier', False):
                suppliers.append(enhanced_contact)
            else:
                customers.append(enhanced_contact)
        
        print(f"  → Customers: {len(customers)}")
        print(f"  → Suppliers/Vendors: {len(suppliers)}")
        
        if customers:
            print(f"\n Sample Customer Data:")
            sample = customers[0]
            print(f"  External ID: {sample['external_id']}")
            print(f"  Name: {sample['name']}")
            print(f"  Email: {sample['primary_email']}")
            print(f"  Phone: {sample['primary_phone']}")
            
        # Save data
        os.makedirs('data', exist_ok=True)
        with open('data/customers.json', 'w') as f:
            json.dump(customers, f, indent=2)
            
        with open('data/suppliers.json', 'w') as f:
            json.dump(suppliers, f, indent=2)
            
        print(f"\n✓ Saved to data/customers.json ({len(customers)} customers)")
    else:
        print(f" Error: {response.text}")
        customers = []
except Exception as e:
    print(f" Exception: {str(e)}")
    import traceback
    traceback.print_exc()
    customers = []

# ============================================================================
# STEP 2: Fetch ALL Invoices (Customer AR only, not Bills/AP)
# ============================================================================
print("\n[STEP 2] Fetching Invoices from QuickBooks...")
try:
    response = requests.get(f"{BASE_URL}/invoice", headers=headers)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        all_invoices = response.json()
        print(f"✓ Total invoices retrieved: {len(all_invoices)}")
        
        # Filter for customer invoices (AR), exclude bills (AP)
        customer_invoices = []
        outstanding_invoices = []
        paid_invoices = []
        
        total_ar_outstanding = 0
        total_ar_paid = 0
        
        for inv in all_invoices:
            inv_type = (inv.get('type') or '').upper()
            
            # Skip bills/vendor bills (these are AP, not AR)
            if inv_type in ['BILL', 'VENDOR_BILL', 'VENDOR BILL']:
                continue
            
            # Extract amounts - check multiple possible field names
            # IMPORTANT: Unified.to uses 'balance_amount' not 'balance'!
            raw = inv
            total_amount = get_amount(raw, 'total_amount') or get_amount(raw, 'total') or get_amount(raw, 'amount')
            balance = get_amount(raw, 'balance_amount') or get_amount(raw, 'balance') or get_amount(raw, 'amount_due')
            amount_paid = get_amount(raw, 'paid_amount') or get_amount(raw, 'amount_paid') or (total_amount - balance)
            
            # Parse dates
            invoice_date = parse_date(inv.get('invoice_date') or inv.get('date') or inv.get('invoice_at'))
            due_date = parse_date(inv.get('due_date') or inv.get('due_at'))
            posted_date = parse_date(inv.get('posted_at') or inv.get('posted_date'))
            
            # Calculate days overdue
            days_overdue = 0
            if due_date and balance > 0:
                days_overdue = max(0, (datetime.now() - due_date).days)
            
            # Determine status
            status_raw = (inv.get('status') or 'OPEN').upper()
            if balance <= 0.01:
                status = 'PAID'
            elif amount_paid > 0:
                status = 'PARTIAL'
            elif days_overdue > 0:
                status = 'OVERDUE'
            else:
                status = 'OPEN'
            
            # Determine aging bucket
            if days_overdue <= 0:
                aging_bucket = 'Current'
            elif days_overdue <= 30:
                aging_bucket = '1-30'
            elif days_overdue <= 60:
                aging_bucket = '31-60'
            elif days_overdue <= 90:
                aging_bucket = '61-90'
            elif days_overdue <= 120:
                aging_bucket = '91-120'
            else:
                aging_bucket = '120+'
            
            # Enhanced invoice data matching Django model
            enhanced_invoice = {
                'external_id': inv.get('id'),
                'contact_id': inv.get('contact_id') or inv.get('customer_id'),
                'invoice_number': inv.get('invoice_number') or inv.get('number') or inv.get('id'),
                'invoice_at': invoice_date.isoformat() if invoice_date else None,
                'posted_at': posted_date.isoformat() if posted_date else None,
                'due_at': due_date.isoformat() if due_date else None,
                'total_amount': total_amount,
                'tax_amount': get_amount(inv, 'tax_amount') or get_amount(inv, 'tax'),
                'amount_paid': amount_paid,
                'amount_due': balance,
                'currency': inv.get('currency', 'USD'),
                'notes': inv.get('notes') or inv.get('memo'),
                'status': status,
                'days_overdue': days_overdue,
                'aging_bucket': aging_bucket,
                'external_created_at': inv.get('created_at'),
                'external_updated_at': inv.get('updated_at'),
                'raw_data': inv
            }
            
            customer_invoices.append(enhanced_invoice)
            
            # Track outstanding vs paid
            if balance > 0.01:
                outstanding_invoices.append(enhanced_invoice)
                total_ar_outstanding += balance
            else:
                paid_invoices.append(enhanced_invoice)
                total_ar_paid += total_amount
        
        print(f"\n Invoice Analysis:")
        print(f"  → Customer Invoices (AR): {len(customer_invoices)}")
        print(f"  → Outstanding Invoices: {len(outstanding_invoices)}")
        print(f"  → Paid Invoices: {len(paid_invoices)}")
        print(f"  → Total AR Outstanding: ${total_ar_outstanding:,.2f}")
        print(f"  → Total AR Paid: ${total_ar_paid:,.2f}")
        
        if outstanding_invoices:
            print(f"\n Sample Outstanding Invoice:")
            sample = outstanding_invoices[0]
            print(f"  Invoice Number: {sample['invoice_number']}")
            print(f"  Customer ID: {sample['contact_id']}")
            print(f"  Status: {sample['status']}")
            print(f"  Total: ${sample['total_amount']:,.2f}")
            print(f"  Amount Due: ${sample['amount_due']:,.2f}")
            print(f"  Days Overdue: {sample['days_overdue']}")
            print(f"  Aging Bucket: {sample['aging_bucket']}")
        else:
            print(f"\n WARNING: No outstanding invoices found!")
            
        # Save invoice data
        with open('data/customer_invoices.json', 'w') as f:
            json.dump(customer_invoices, f, indent=2)
        
        with open('data/outstanding_invoices.json', 'w') as f:
            json.dump(outstanding_invoices, f, indent=2)
            
        with open('data/paid_invoices.json', 'w') as f:
            json.dump(paid_invoices, f, indent=2)
            
        print(f"\n✓ Saved {len(customer_invoices)} invoices to data/customer_invoices.json")
        
    else:
        print(f" Error: {response.text}")
        customer_invoices = []
        outstanding_invoices = []
except Exception as e:
    print(f" Exception: {str(e)}")
    import traceback
    traceback.print_exc()
    customer_invoices = []
    outstanding_invoices = []

# ============================================================================
# STEP 3: Fetch ALL Transactions (Payments & Refunds)
# ============================================================================
print("\n[STEP 3] Fetching Transactions (Payments & Refunds)...")
try:
    response = requests.get(f"{BASE_URL}/transaction", headers=headers)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        all_transactions = response.json()
        print(f"✓ Total transactions retrieved: {len(all_transactions)}")
        
        # Categorize transactions
        payments = []
        refunds = []
        withdrawals = []
        deposits = []
        other_transactions = []
        
        total_payments_received = 0
        total_refunds_issued = 0
        
        for txn in all_transactions:
            txn_type = (txn.get('type') or '').upper().replace('_', '').replace(' ', '')
            amount = get_amount(txn, 'total_amount') or get_amount(txn, 'amount')
            memo = (txn.get('memo') or '').lower()
            
            # Extract contact from contacts array if available
            contact_id = txn.get('contact_id')
            if not contact_id and txn.get('contacts'):
                contacts = txn.get('contacts', [])
                if contacts and isinstance(contacts[0], dict):
                    contact_id = contacts[0].get('id')
            
            # Determine transaction type from type field OR memo
            determined_type = 'OTHER'
            if txn_type in ['PAYMENT', 'RECEIVEPAYMENT', 'CUSTOMERPAYMENT', 'INVOICEPAYMENT', 'SALESRECEIPT']:
                determined_type = 'PAYMENT'
                payments.append(txn)
                total_payments_received += amount
            elif 'payment' in memo or 'received' in memo or 'deposit' in memo:
                determined_type = 'PAYMENT'
                payments.append(txn)
                total_payments_received += amount
            elif txn_type in ['REFUND', 'CREDITNOTE', 'CREDITMEMO']:
                determined_type = 'REFUND'
                refunds.append(txn)
                total_refunds_issued += amount
            elif 'refund' in memo or 'credit' in memo:
                determined_type = 'REFUND'
                refunds.append(txn)
                total_refunds_issued += amount
            elif txn_type in ['WITHDRAWAL', 'EXPENSE'] or 'withdrawal' in memo:
                determined_type = 'WITHDRAWAL'
                withdrawals.append(txn)
            elif txn_type in ['DEPOSIT']:
                determined_type = 'DEPOSIT'
                deposits.append(txn)
            else:
                other_transactions.append(txn)
            
            # Enhanced transaction data matching Django model
            enhanced_txn = {
                'external_id': txn.get('id'),
                'contact_id': contact_id,
                'memo': txn.get('memo') or txn.get('notes'),
                'total_amount': amount,
                'account_id': txn.get('account_id'),
                'transaction_type': determined_type,
                'transaction_date': txn.get('transaction_date') or txn.get('date'),
                'external_created_at': txn.get('created_at'),
                'external_updated_at': txn.get('updated_at'),
                'raw_data': txn
            }
        
        print(f"\n Transaction Analysis:")
        print(f"  → Payments Received: {len(payments)} (${total_payments_received:,.2f})")
        print(f"  → Refunds Issued: {len(refunds)} (${total_refunds_issued:,.2f})")
        print(f"  → Withdrawals: {len(withdrawals)}")
        print(f"  → Deposits: {len(deposits)}")
        print(f"  → Other Transactions: {len(other_transactions)}")
        print(f"  → Net Received: ${(total_payments_received - total_refunds_issued):,.2f}")
        
        # Show all unique transaction types for debugging
        unique_types = sorted(set(t.get('type', 'UNKNOWN') for t in all_transactions))
        print(f"\n All Transaction Types Found: {', '.join(unique_types)}")
        
        if payments:
            print(f"\n Sample Payment Transaction:")
            sample = payments[0]
            print(f"  Type: {sample.get('type')}")
            print(f"  Amount: ${get_amount(sample, 'total_amount'):,.2f}")
            print(f"  Customer ID: {sample.get('contact_id')}")
            print(f"  Date: {sample.get('transaction_date') or sample.get('date')}")
        
        # Save transaction data
        enhanced_payments = []
        enhanced_refunds = []
        enhanced_all_txns = []
        
        for txn in all_transactions:
            txn_type = (txn.get('type') or '').upper().replace('_', '').replace(' ', '')
            amount = get_amount(txn, 'total_amount') or get_amount(txn, 'amount')
            memo = (txn.get('memo') or '').lower()
            
            contact_id = txn.get('contact_id')
            if not contact_id and txn.get('contacts'):
                contacts = txn.get('contacts', [])
                if contacts and isinstance(contacts[0], dict):
                    contact_id = contacts[0].get('id')
            
            # Determine type from field OR memo keywords
            if txn_type in ['PAYMENT', 'RECEIVEPAYMENT', 'CUSTOMERPAYMENT', 'INVOICEPAYMENT', 'SALESRECEIPT']:
                determined_type = 'PAYMENT'
            elif 'payment' in memo or 'received' in memo or 'deposit' in memo:
                determined_type = 'PAYMENT'
            elif txn_type in ['REFUND', 'CREDITNOTE', 'CREDITMEMO']:
                determined_type = 'REFUND'
            elif 'refund' in memo or 'credit' in memo:
                determined_type = 'REFUND'
            elif txn_type in ['WITHDRAWAL', 'EXPENSE'] or 'withdrawal' in memo:
                determined_type = 'WITHDRAWAL'
            elif txn_type in ['DEPOSIT']:
                determined_type = 'DEPOSIT'
            else:
                determined_type = 'OTHER'
            
            enhanced = {
                'external_id': txn.get('id'),
                'contact_id': contact_id,
                'memo': txn.get('memo') or txn.get('notes'),
                'total_amount': amount,
                'account_id': txn.get('account_id'),
                'transaction_type': determined_type,
                'transaction_date': txn.get('transaction_date') or txn.get('date'),
                'external_created_at': txn.get('created_at'),
                'external_updated_at': txn.get('updated_at'),
                'raw_data': txn
            }
            
            enhanced_all_txns.append(enhanced)
            
            if determined_type == 'PAYMENT':
                enhanced_payments.append(enhanced)
            elif determined_type == 'REFUND':
                enhanced_refunds.append(enhanced)
        
        with open('data/all_transactions.json', 'w') as f:
            json.dump(enhanced_all_txns, f, indent=2)
            
        with open('data/payments.json', 'w') as f:
            json.dump(enhanced_payments, f, indent=2)
        
        with open('data/refunds.json', 'w') as f:
            json.dump(enhanced_refunds, f, indent=2)
            
        print(f"\n✓ Saved {len(enhanced_payments)} payments to data/payments.json")
        print(f"✓ Saved {len(enhanced_refunds)} refunds to data/refunds.json")
        
    else:
        print(f" Error: {response.text}")
        enhanced_payments = []
        enhanced_refunds = []
except Exception as e:
    print(f" Exception: {str(e)}")
    import traceback
    traceback.print_exc()
    enhanced_payments = []
    enhanced_refunds = []

# ============================================================================
# STEP 4: Generate AR Aging Report with Full Metrics
# ============================================================================
print("\n[STEP 4] Generating AR Aging Report...")
try:
    aging_report = []
    today = datetime.now().date()
    
    bucket_totals = {
        'Current': 0,
        '1-30': 0,
        '31-60': 0,
        '61-90': 0,
        '91-120': 0,
        '120+': 0
    }
    
    bucket_counts = {
        'Current': 0,
        '1-30': 0,
        '31-60': 0,
        '61-90': 0,
        '91-120': 0,
        '120+': 0
    }
    
    for invoice in outstanding_invoices:
        bucket = invoice['aging_bucket']
        amount = invoice['amount_due']
        
        bucket_totals[bucket] += amount
        bucket_counts[bucket] += 1
        
        aging_report.append({
            'invoice_id': invoice['external_id'],
            'invoice_number': invoice['invoice_number'],
            'contact_id': invoice['contact_id'],
            'invoice_date': invoice['invoice_at'],
            'due_date': invoice['due_at'],
            'days_overdue': invoice['days_overdue'],
            'aging_bucket': bucket,
            'outstanding_balance': amount,
            'total_amount': invoice['total_amount'],
            'amount_paid': invoice['amount_paid'],
            'status': invoice['status']
        })
    
    # Sort by days overdue (most overdue first)
    aging_report.sort(key=lambda x: x['days_overdue'], reverse=True)
    
    with open('data/ar_aging_report.json', 'w') as f:
        json.dump(aging_report, f, indent=2)
    
    print(f"\n AR Aging Buckets:")
    print(f"  {'Bucket':<15} {'Count':>8} {'Amount':>15}")
    print(f"  {'-' * 40}")
    
    grand_total = 0
    total_invoices = 0
    for bucket in ['Current', '1-30', '31-60', '61-90', '91-120', '120+']:
        amount = bucket_totals[bucket]
        count = bucket_counts[bucket]
        grand_total += amount
        total_invoices += count
        if amount > 0:
            print(f"  {bucket:<15} {count:>8} ${amount:>14,.2f}")
    
    print(f"  {'─' * 40}")
    print(f"  {'TOTAL':<15} {total_invoices:>8} ${grand_total:>14,.2f}")
    
    # Calculate additional AR metrics
    overdue_amount = sum(bucket_totals[b] for b in ['1-30', '31-60', '61-90', '91-120', '120+'])
    overdue_count = sum(bucket_counts[b] for b in ['1-30', '31-60', '61-90', '91-120', '120+'])
    
    print(f"\n AR Metrics:")
    print(f"  → Total Outstanding: ${grand_total:,.2f}")
    print(f"  → Current (Not Due): ${bucket_totals['Current']:,.2f}")
    print(f"  → Overdue: ${overdue_amount:,.2f}")
    print(f"  → % Overdue: {(overdue_amount/grand_total*100 if grand_total > 0 else 0):.1f}%")
    print(f"  → Average Invoice: ${(grand_total/total_invoices if total_invoices > 0 else 0):,.2f}")
    
    print(f"\n✓ Saved AR aging report to data/ar_aging_report.json")
    
except Exception as e:
    print(f" Exception: {str(e)}")
    import traceback
    traceback.print_exc()

# ============================================================================
# STEP 5: Create Customer AR Summary (for ARAgingSummary model)
# ============================================================================
print("\n[STEP 5] Creating Customer AR Summary...")
try:
    customer_ar_summaries = []
    
    # Group invoices by customer
    customer_invoices_map = defaultdict(list)
    for invoice in outstanding_invoices:
        customer_id = invoice['contact_id']
        if customer_id:
            customer_invoices_map[customer_id].append(invoice)
    
    for customer in customers:
        customer_id = customer['external_id']
        customer_outstanding_invoices = customer_invoices_map.get(customer_id, [])
        
        if not customer_outstanding_invoices:
            continue
        
        # Calculate aging buckets for this customer
        current = sum(inv['amount_due'] for inv in customer_outstanding_invoices if inv['aging_bucket'] == 'Current')
        days_1_30 = sum(inv['amount_due'] for inv in customer_outstanding_invoices if inv['aging_bucket'] == '1-30')
        days_31_60 = sum(inv['amount_due'] for inv in customer_outstanding_invoices if inv['aging_bucket'] == '31-60')
        days_61_90 = sum(inv['amount_due'] for inv in customer_outstanding_invoices if inv['aging_bucket'] == '61-90')
        days_91_120 = sum(inv['amount_due'] for inv in customer_outstanding_invoices if inv['aging_bucket'] == '91-120')
        days_120_plus = sum(inv['amount_due'] for inv in customer_outstanding_invoices if inv['aging_bucket'] == '120+')
        
        total_outstanding = sum(inv['amount_due'] for inv in customer_outstanding_invoices)
        total_overdue = days_1_30 + days_31_60 + days_61_90 + days_91_120 + days_120_plus
        overdue_invoices = sum(1 for inv in customer_outstanding_invoices if inv['days_overdue'] > 0)
        
        customer_ar_summaries.append({
            'customer_id': customer_id,
            'customer_name': customer['name'],
            'customer_email': customer['primary_email'],
            'current': current,
            'days_1_30': days_1_30,
            'days_31_60': days_31_60,
            'days_61_90': days_61_90,
            'days_91_120': days_91_120,
            'days_120_plus': days_120_plus,
            'total_outstanding': total_outstanding,
            'total_overdue': total_overdue,
            'total_invoices': len(customer_outstanding_invoices),
            'overdue_invoices': overdue_invoices,
            'percent_overdue': round((total_overdue / total_outstanding * 100) if total_outstanding > 0 else 0, 2)
        })
    
    # Sort by total outstanding (highest first)
    customer_ar_summaries.sort(key=lambda x: x['total_outstanding'], reverse=True)
    
    with open('data/customer_ar_summary.json', 'w') as f:
        json.dump(customer_ar_summaries, f, indent=2)
    
    print(f"✓ Found {len(customer_ar_summaries)} customers with outstanding balances")
    
    if customer_ar_summaries:
        print(f"\n Top 5 Customers by Outstanding Balance:")
        for i, cust in enumerate(customer_ar_summaries[:5], 1):
            print(f"  {i}. {cust['customer_name']}")
            print(f"     Outstanding: ${cust['total_outstanding']:,.2f} | Overdue: ${cust['total_overdue']:,.2f} ({cust['percent_overdue']:.1f}%)")
            print(f"     Invoices: {cust['total_invoices']} total, {cust['overdue_invoices']} overdue")
    
    print(f"\n✓ Saved to data/customer_ar_summary.json")
    
except Exception as e:
    print(f" Exception: {str(e)}")
    import traceback
    traceback.print_exc()

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 90)
print("DATA EXTRACTION COMPLETE - Ready for Dagster ETL Pipeline")
print("=" * 90)

print(f"\n Files Created for Django Models:")
print(f"  1. data/customers.json              → Customer model ({len(customers)} records)")
print(f"  2. data/customer_invoices.json      → Invoice model ({len(customer_invoices)} records)")
print(f"  3. data/outstanding_invoices.json   → Invoice model - Outstanding only")
print(f"  4. data/payments.json               → Transaction model - Payments ({len(enhanced_payments)} records)")
print(f"  5. data/refunds.json                → Transaction model - Refunds ({len(enhanced_refunds)} records)")
print(f"  6. data/all_transactions.json       → Transaction model - All types")
print(f"  7. data/ar_aging_report.json        → Pre-calculated aging data")
print(f"  8. data/customer_ar_summary.json    → ARAgingSummary model")

print(f"\n Critical AR Dashboard Metrics:")
print(f"  → Total Customers: {len(customers)}")
print(f"  → Total AR Outstanding: ${total_ar_outstanding:,.2f}")
print(f"  → Outstanding Invoices: {len(outstanding_invoices)}")
print(f"  → Payments Received: ${total_payments_received:,.2f}")
print(f"  → Refunds Issued: ${total_refunds_issued:,.2f}")
print(f"  → Net Collections: ${(total_payments_received - total_refunds_issued):,.2f}")
print(f"  → Customers with AR: {len(customer_ar_summaries)}")

if len(outstanding_invoices) == 0:
    print(f"\n  TROUBLESHOOTING: No outstanding invoices found!")
    print(f"  Possible reasons:")
    print(f"    1. All invoices in QuickBooks sandbox are marked as paid")
    print(f"    2. The 'balance' or 'amount_due' fields are not syncing")
    print(f"    3. QuickBooks connection needs to be refreshed in Unified.to")
    print(f"  Action: Check data/customer_invoices.json to see raw invoice data")

print(f"\n Next Steps for Dagster Pipeline:")
print(f"  1. Create Dagster assets to load these JSON files")
print(f"  2. Transform data to match Django model fields exactly")
print(f"  3. Calculate aging buckets in real-time during ETL")
print(f"  4. Load into PostgreSQL using Django ORM")
print(f"  5. Build HTMX views with Apache ECharts visualizations")
print(f"  6. Create both table view and widget dashboard views")

print(f"\n AR Dashboard Components Needed:")
print(f"  ✓ Total AR Outstanding (KPI)")
print(f"  ✓ Aging Buckets Chart (Bar/Pie)")
print(f"  ✓ Customer AR Ranking (Table)")
print(f"  ✓ Payment History Timeline")
print(f"  ✓ Overdue Invoice Alert List")
print(f"  ✓ Collections Performance (Payments vs Refunds)")
print(f"  ✓ Days Sales Outstanding (DSO) calculation")