"""
Dagster ETL Pipeline for HeronAI AR Dashboard
Extracts QuickBooks data via Unified.to and loads into PostgreSQL
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from decimal import Decimal

import django
import pandas as pd
from dagster import (
    asset, 
    AssetExecutionContext, 
    Output, 
    MetadataValue,
    define_asset_job,
    AssetSelection,
    ScheduleDefinition
)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from ar_dashboard.models import Customer, Invoice, Transaction, ARAgingSummary

# Path to your JSON data files
DATA_DIR = Path(__file__).parent.parent / 'data'

# ==============================================================================
# EXTRACT ASSETS - Read raw data from JSON files
# ==============================================================================

@asset(group_name="extract")
def raw_customers(context: AssetExecutionContext) -> List[dict]:
    """Extract raw customer data from JSON file"""
    file_path = DATA_DIR / 'customers.json'
    context.log.info(f"Reading customers from {file_path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"Customer data file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    context.log.info(f"✓ Extracted {len(data)} customers")
    return data


@asset(group_name="extract")
def raw_invoices(context: AssetExecutionContext) -> List[dict]:
    """Extract raw invoice data from JSON file"""
    # Use customer_invoices.json (the correct file from extraction)
    file_path = DATA_DIR / 'customer_invoices.json'
    context.log.info(f"Reading invoices from {file_path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"Invoice data file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    context.log.info(f"✓ Extracted {len(data)} invoices")
    return data


@asset(group_name="extract")
def raw_transactions(context: AssetExecutionContext) -> List[dict]:
    """Extract raw transaction data from JSON file"""
    # Use all_transactions.json (the correct file from extraction)
    file_path = DATA_DIR / 'all_transactions.json'
    context.log.info(f"Reading transactions from {file_path}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"Transaction data file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    context.log.info(f"✓ Extracted {len(data)} transactions")
    return data


# ==============================================================================
# TRANSFORM ASSETS - Clean and structure data
# ==============================================================================

@asset(group_name="transform", deps=[raw_customers])
def transformed_customers(context: AssetExecutionContext, raw_customers: List[dict]) -> pd.DataFrame:
    """Transform customer data into structured format"""
    customers = []
    
    for customer in raw_customers:
        # Extract email - check if it's already extracted or nested
        primary_email = customer.get('primary_email')
        if not primary_email and customer.get('emails'):
            emails = customer.get('emails', [])
            primary_email = emails[0].get('email') if emails and isinstance(emails[0], dict) else None
        
        # Extract phone - check if it's already extracted or nested
        primary_phone = customer.get('primary_phone')
        if not primary_phone and customer.get('telephones'):
            phones = customer.get('telephones', [])
            primary_phone = phones[0].get('telephone') if phones and isinstance(phones[0], dict) else None
        
        # Parse dates
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                return None
        
        created_at = parse_date(customer.get('external_created_at') or customer.get('created_at'))
        updated_at = parse_date(customer.get('external_updated_at') or customer.get('updated_at'))
        
        customers.append({
            'external_id': customer.get('external_id') or customer.get('id'),
            'name': customer.get('name', 'Unknown'),
            'primary_email': primary_email,
            'primary_phone': primary_phone,
            'external_created_at': created_at,
            'external_updated_at': updated_at,
            'raw_data': customer.get('raw_data') or customer
        })
    
    df = pd.DataFrame(customers)
    context.log.info(f"✓ Transformed {len(df)} customers")
    
    return df



@asset(group_name="transform", deps=[raw_invoices])
def transformed_invoices(context: AssetExecutionContext, raw_invoices: List[dict]) -> pd.DataFrame:
    """Transform invoice data with aging calculations"""
    invoices = []
    today = datetime.now(timezone.utc)
    
    for invoice in raw_invoices:
        # Parse dates
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except:
                return None
        
        invoice_at = parse_date(invoice.get('invoice_at'))
        posted_at = parse_date(invoice.get('posted_at'))
        due_at = parse_date(invoice.get('due_at'))
        created_at = parse_date(invoice.get('external_created_at') or invoice.get('created_at'))
        updated_at = parse_date(invoice.get('external_updated_at') or invoice.get('updated_at'))
        
        # Extract amounts - NO DIVISION BY 100! Data is already in dollars
        def safe_decimal(value):
            if value is None:
                return Decimal('0.00')
            try:
                return Decimal(str(value))
            except:
                return Decimal('0.00')
        
        total_amount = safe_decimal(invoice.get('total_amount'))
        tax_amount = safe_decimal(invoice.get('tax_amount'))
        amount_paid = safe_decimal(invoice.get('amount_paid'))
        amount_due = safe_decimal(invoice.get('amount_due'))
        
        # Calculate days overdue and aging bucket
        days_overdue = 0
        aging_bucket = 'Current'
        
        if due_at and amount_due > 0:
            days_overdue = max(0, (today - due_at).days)
            
            if days_overdue == 0:
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
        
        # Determine status
        status = 'OPEN'
        if amount_due <= 0:
            status = 'PAID'
        elif amount_paid > 0:
            status = 'PARTIAL'
        elif days_overdue > 0:
            status = 'OVERDUE'
        
        invoices.append({
            'external_id': invoice.get('external_id') or invoice.get('id'),
            'contact_id': invoice.get('contact_id'),
            'invoice_number': invoice.get('invoice_number', 'N/A'),
            'invoice_at': invoice_at,
            'posted_at': posted_at,
            'due_at': due_at,
            'total_amount': total_amount,
            'tax_amount': tax_amount,
            'amount_paid': amount_paid,
            'amount_due': amount_due,
            'currency': invoice.get('currency', 'USD'),
            'notes': invoice.get('notes'),
            'status': status,
            'days_overdue': days_overdue,
            'aging_bucket': aging_bucket,
            'external_created_at': created_at,
            'external_updated_at': updated_at,
            'raw_data': invoice.get('raw_data') or invoice
        })
    
    df = pd.DataFrame(invoices)
    context.log.info(f"✓ Transformed {len(df)} invoices")
    context.log.info(f"  → Outstanding invoices: {len(df[df['amount_due'] > 0])}")
    context.log.info(f"  → Total AR: ${df['amount_due'].sum():,.2f}")
    
    return df


@asset(group_name="transform", deps=[raw_transactions])
def transformed_transactions(context: AssetExecutionContext, raw_transactions: List[dict]) -> pd.DataFrame:
    """Transform transaction/payment data"""
    transactions = []
    
    for txn in raw_transactions:
        # Parse dates
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                return None
        
        created_at = parse_date(txn.get('external_created_at') or txn.get('created_at'))
        updated_at = parse_date(txn.get('external_updated_at') or txn.get('updated_at'))
        
        # Extract amount - NO DIVISION BY 100! Data is already in dollars
        def safe_decimal(value):
            if value is None:
                return Decimal('0.00')
            try:
                return Decimal(str(value))
            except:
                return Decimal('0.00')
        
        total_amount = safe_decimal(txn.get('total_amount'))
        
        # Get transaction type
        txn_type = (txn.get('transaction_type') or 'OTHER').upper()
        if txn_type not in ['PAYMENT', 'REFUND', 'WITHDRAWAL', 'DEPOSIT']:
            txn_type = 'OTHER'
        
        transactions.append({
            'external_id': txn.get('external_id') or txn.get('id'),
            'contact_id': txn.get('contact_id'),
            'memo': txn.get('memo'),
            'total_amount': total_amount,
            'account_id': txn.get('account_id'),
            'transaction_type': txn_type,
            'external_created_at': created_at,
            'external_updated_at': updated_at,
            'raw_data': txn.get('raw_data') or txn
        })
    
    df = pd.DataFrame(transactions)
    context.log.info(f"✓ Transformed {len(df)} transactions")
    
    # Log transaction type breakdown
    if not df.empty:
        type_counts = df['transaction_type'].value_counts()
        context.log.info(f"  Transaction breakdown:")
        for txn_type, count in type_counts.items():
            context.log.info(f"    → {txn_type}: {count}")
    
    return df


# ==============================================================================
# LOAD ASSETS - Write to PostgreSQL via Django ORM
# ==============================================================================

@asset(group_name="load", deps=[transformed_customers])
def load_customers(context: AssetExecutionContext, transformed_customers: pd.DataFrame) -> Output[int]:
    """Load transformed customer data into Django model"""
    created_count = 0
    updated_count = 0
    
    for _, row in transformed_customers.iterrows():
        customer, created = Customer.objects.update_or_create(
            external_id=row['external_id'],
            defaults={
                'name': row['name'],
                'primary_email': row['primary_email'],
                'primary_phone': row['primary_phone'],
                'external_created_at': row['external_created_at'],
                'external_updated_at': row['external_updated_at'],
                'raw_data': row['raw_data']
            }
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
    
    total = created_count + updated_count
    context.log.info(f"✓ Loaded {total} customers ({created_count} created, {updated_count} updated)")
    
    return Output(
        total,
        metadata={
            "total_customers": MetadataValue.int(total),
            "created": MetadataValue.int(created_count),
            "updated": MetadataValue.int(updated_count)
        }
    )


@asset(group_name="load", deps=[transformed_invoices, load_customers])
def load_invoices(context: AssetExecutionContext, transformed_invoices: pd.DataFrame) -> Output[int]:
    """Load transformed invoice data into Django model and link to customers"""
    created_count = 0
    updated_count = 0
    linked_count = 0
    
    for _, row in transformed_invoices.iterrows():
        # Find customer by contact_id
        customer = None
        if row['contact_id']:
            customer = Customer.objects.filter(external_id=row['contact_id']).first()
            if customer:
                linked_count += 1
        
        invoice, created = Invoice.objects.update_or_create(
            external_id=row['external_id'],
            defaults={
                'contact_id': row['contact_id'],
                'customer': customer,  # Link to Customer object
                'invoice_number': row['invoice_number'],
                'invoice_at': row['invoice_at'],
                'posted_at': row['posted_at'],
                'due_at': row['due_at'],
                'total_amount': row['total_amount'],
                'tax_amount': row['tax_amount'],
                'amount_paid': row['amount_paid'],
                'amount_due': row['amount_due'],
                'currency': row['currency'],
                'notes': row['notes'],
                'status': row['status'],
                'days_overdue': row['days_overdue'],
                'aging_bucket': row['aging_bucket'],
                'external_created_at': row['external_created_at'],
                'external_updated_at': row['external_updated_at'],
                'raw_data': row['raw_data']
            }
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
    
    total = created_count + updated_count
    outstanding_total = transformed_invoices[transformed_invoices['amount_due'] > 0]['amount_due'].sum()
    
    context.log.info(f"✓ Loaded {total} invoices ({created_count} created, {updated_count} updated)")
    context.log.info(f"  → Linked to customers: {linked_count}")
    context.log.info(f"  → Total AR Outstanding: ${outstanding_total:,.2f}")
    
    return Output(
        total,
        metadata={
            "total_invoices": MetadataValue.int(total),
            "created": MetadataValue.int(created_count),
            "updated": MetadataValue.int(updated_count),
            "linked_to_customers": MetadataValue.int(linked_count),
            "total_ar_outstanding": MetadataValue.float(float(outstanding_total))
        }
    )


@asset(group_name="load", deps=[transformed_transactions, load_customers])
def load_transactions(context: AssetExecutionContext, transformed_transactions: pd.DataFrame) -> Output[int]:
    """Load transformed transaction data into Django model and link to customers"""
    created_count = 0
    updated_count = 0
    linked_count = 0
    
    for _, row in transformed_transactions.iterrows():
        # Find customer by contact_id
        customer = None
        if row['contact_id']:
            customer = Customer.objects.filter(external_id=row['contact_id']).first()
            if customer:
                linked_count += 1
        
        txn, created = Transaction.objects.update_or_create(
            external_id=row['external_id'],
            defaults={
                'contact_id': row['contact_id'],
                'customer': customer,  # Link to Customer object
                'memo': row['memo'],
                'total_amount': row['total_amount'],
                'account_id': row['account_id'],
                'transaction_type': row['transaction_type'],
                'external_created_at': row['external_created_at'],
                'external_updated_at': row['external_updated_at'],
                'raw_data': row['raw_data']
            }
        )
        if created:
            created_count += 1
        else:
            updated_count += 1
    
    total = created_count + updated_count
    context.log.info(f"✓ Loaded {total} transactions ({created_count} created, {updated_count} updated)")
    context.log.info(f"  → Linked to customers: {linked_count}")
    
    return Output(
        total,
        metadata={
            "total_transactions": MetadataValue.int(total),
            "created": MetadataValue.int(created_count),
            "updated": MetadataValue.int(updated_count),
            "linked_to_customers": MetadataValue.int(linked_count)
        }
    )


@asset(group_name="load", deps=[load_invoices])
def load_ar_aging_summary(context: AssetExecutionContext, transformed_invoices: pd.DataFrame) -> Output[int]:
    """Calculate and load AR aging summary by customer"""
    try:
        if transformed_invoices.empty:
            context.log.warning("No invoices found — skipping AR aging summary load.")
            return Output(0, metadata={"rows_loaded": MetadataValue.int(0)})
        
        # Ensure numeric types
        transformed_invoices['amount_due'] = pd.to_numeric(
            transformed_invoices['amount_due'], 
            errors='coerce'
        ).fillna(0)
        
        # Only include outstanding invoices
        outstanding = transformed_invoices[transformed_invoices['amount_due'] > 0].copy()
        
        if outstanding.empty:
            context.log.warning("No outstanding invoices found — AR summary will be empty.")
            ARAgingSummary.objects.all().delete()
            return Output(0, metadata={"rows_loaded": MetadataValue.int(0)})
        
        # Group by customer and aging bucket
        summary_pivot = (
            outstanding
            .pivot_table(
                index='contact_id',
                columns='aging_bucket',
                values='amount_due',
                aggfunc='sum',
                fill_value=0
            )
            .reset_index()
        )
        
        # Rename columns to match model fields
        column_mapping = {
            "Current": "current",
            "1-30": "days_1_30",
            "31-60": "days_31_60",
            "61-90": "days_61_90",
            "91-120": "days_91_120",
            "120+": "days_120_plus",
        }
        
        summary_pivot = summary_pivot.rename(columns=column_mapping)
        
        # Ensure all bucket columns exist
        bucket_cols = ["current", "days_1_30", "days_31_60", "days_61_90", "days_91_120", "days_120_plus"]
        for col in bucket_cols:
            if col not in summary_pivot.columns:
                summary_pivot[col] = 0
        
        # Calculate totals
        summary_pivot["total_outstanding"] = summary_pivot[bucket_cols].sum(axis=1)
        overdue_cols = ["days_1_30", "days_31_60", "days_61_90", "days_91_120", "days_120_plus"]
        summary_pivot["total_overdue"] = summary_pivot[overdue_cols].sum(axis=1)
        
        # Calculate invoice counts per customer
        invoice_counts = outstanding.groupby('contact_id').agg({
            'external_id': 'count',  # total invoices
            'days_overdue': lambda x: (x > 0).sum()  # overdue invoices
        }).reset_index()
        invoice_counts.columns = ['contact_id', 'total_invoices', 'overdue_invoices']
        
        # Merge counts into summary
        summary_pivot = summary_pivot.merge(invoice_counts, on='contact_id', how='left')
        
        # Clear existing summaries and reload
        ARAgingSummary.objects.all().delete()
        count = 0
        
        for _, row in summary_pivot.iterrows():
            customer = Customer.objects.filter(external_id=row["contact_id"]).first()
            if not customer:
                context.log.warning(f"Customer not found for contact_id: {row['contact_id']}")
                continue
            
            ARAgingSummary.objects.create(
                customer=customer,
                current=Decimal(str(row.get("current", 0))),
                days_1_30=Decimal(str(row.get("days_1_30", 0))),
                days_31_60=Decimal(str(row.get("days_31_60", 0))),
                days_61_90=Decimal(str(row.get("days_61_90", 0))),
                days_91_120=Decimal(str(row.get("days_91_120", 0))),
                days_120_plus=Decimal(str(row.get("days_120_plus", 0))),
                total_outstanding=Decimal(str(row.get("total_outstanding", 0))),
                total_overdue=Decimal(str(row.get("total_overdue", 0))),
                total_invoices=int(row.get("total_invoices", 0)),
                overdue_invoices=int(row.get("overdue_invoices", 0))
            )
            count += 1
        
        total_ar = summary_pivot["total_outstanding"].sum()
        context.log.info(f"✓ Loaded {count} AR aging summary records")
        context.log.info(f"  → Total AR Outstanding: ${total_ar:,.2f}")
        
        return Output(
            count,
            metadata={
                "customers_with_ar": MetadataValue.int(count),
                "total_ar_outstanding": MetadataValue.float(float(total_ar))
            }
        )
    
    except Exception as e:
        context.log.error(f"Error in load_ar_aging_summary: {e}", exc_info=True)
        raise


# ==============================================================================
# DAGSTER JOBS & SCHEDULES
# ==============================================================================

# Job 1: Full ETL Pipeline (Extract → Transform → Load)
full_etl_job = define_asset_job(
    name="full_ar_etl_pipeline",
    description="Complete ETL pipeline: Extract QuickBooks data, transform, and load into PostgreSQL",
    selection=AssetSelection.all()
)

# Job 2: Extract Only (for testing data extraction)
extract_only_job = define_asset_job(
    name="extract_quickbooks_data",
    description="Extract data from QuickBooks via Unified.to (no transform or load)",
    selection=AssetSelection.groups("extract")
)

# Job 3: Transform Only (for testing transformations)
transform_only_job = define_asset_job(
    name="transform_data",
    description="Transform extracted data (assumes extract has run)",
    selection=AssetSelection.groups("transform")
)

# Job 4: Load Only (for reloading data)
load_only_job = define_asset_job(
    name="load_to_database",
    description="Load transformed data into PostgreSQL (assumes extract & transform have run)",
    selection=AssetSelection.groups("load")
)

# Job 5: Refresh AR Summary Only (for quick dashboard updates)
refresh_ar_summary_job = define_asset_job(
    name="refresh_ar_aging_summary",
    description="Recalculate AR aging summary from existing invoice data",
    selection=AssetSelection.assets(load_ar_aging_summary)
)

# Schedule: Run full ETL daily at 6 AM
daily_etl_schedule = ScheduleDefinition(
    name="daily_ar_etl",
    job=full_etl_job,
    cron_schedule="0 6 * * *",  # Every day at 6:00 AM
    execution_timezone="America/New_York"
)

# Schedule: Refresh AR summary every 4 hours
ar_summary_refresh_schedule = ScheduleDefinition(
    name="ar_summary_refresh",
    job=refresh_ar_summary_job,
    cron_schedule="0 */4 * * *",  # Every 4 hours
    execution_timezone="America/New_York"
)