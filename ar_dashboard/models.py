from django.db import models
from django.utils import timezone
from decimal import Decimal


class Customer(models.Model):
    """Store customer information from QuickBooks via Unified.to"""
    # Unified.to fields
    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    
    # Contact info (from nested arrays)
    primary_email = models.EmailField(blank=True, null=True)
    primary_phone = models.CharField(max_length=50, blank=True, null=True)
    
    # Metadata
    external_created_at = models.DateTimeField(blank=True, null=True)
    external_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    raw_data = models.JSONField(blank=True, null=True)  # Store full API response
    
    class Meta:
        db_table = 'ar_dashboard_customer'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Invoice(models.Model):
    """Store invoice information from QuickBooks via Unified.to"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('OPEN', 'Open'),
        ('PAID', 'Paid'),
        ('PARTIAL', 'Partially Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    # Unified.to fields
    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    contact_id = models.CharField(max_length=255, db_index=True)  # Links to customer external_id
    customer = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        related_name='invoices',
        null=True,
        blank=True
    )
    
    invoice_number = models.CharField(max_length=100)
    
    # Dates - note the field names from Unified.to
    invoice_at = models.DateTimeField()  # invoice_at from API
    posted_at = models.DateTimeField(blank=True, null=True)  # posted_at from API
    due_at = models.DateTimeField()  # due_at from API (this is the due date)
    
    # Amounts (stored in cents in API, we'll convert to dollars)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)  # Total invoice amount
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)  # Outstanding amount
    
    currency = models.CharField(max_length=10, default='USD')
    notes = models.TextField(blank=True, null=True)
    
    # Status (calculated based on amounts and dates)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    
    # Calculated fields (populated by Dagster pipeline)
    days_overdue = models.IntegerField(default=0)
    aging_bucket = models.CharField(max_length=20, blank=True, null=True)
    
    # Metadata
    external_created_at = models.DateTimeField(blank=True, null=True)
    external_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    raw_data = models.JSONField(blank=True, null=True)
    
    class Meta:
        db_table = 'ar_dashboard_invoice'
        ordering = ['-invoice_at']
        indexes = [
            models.Index(fields=['due_at']),
            models.Index(fields=['status']),
            models.Index(fields=['aging_bucket']),
            models.Index(fields=['contact_id']),
        ]
    
    def __str__(self):
        customer_name = self.customer.name if self.customer else self.contact_id
        return f"{self.invoice_number} - {customer_name}"
    
    def calculate_days_overdue(self):
        """Calculate days overdue from due date"""
        if self.amount_due <= 0:  # Fully paid
            return 0
        
        today = timezone.now().date()
        due_date = self.due_at.date() if hasattr(self.due_at, 'date') else self.due_at
        
        if due_date < today:
            return (today - due_date).days
        return 0
    
    def get_aging_bucket(self):
        """Determine which aging bucket this invoice falls into"""
        days = self.calculate_days_overdue()
        
        if days <= 0:
            return 'Current'
        elif days <= 30:
            return '1-30'
        elif days <= 60:
            return '31-60'
        elif days <= 90:
            return '61-90'
        elif days <= 120:
            return '91-120'
        else:
            return '120+'
    
    def update_status(self):
        """Update invoice status based on amounts and dates"""
        if self.amount_due <= 0:
            self.status = 'PAID'
        elif self.amount_paid > 0:
            self.status = 'PARTIAL'
        elif self.calculate_days_overdue() > 0:
            self.status = 'OVERDUE'
        else:
            self.status = 'OPEN'


class Transaction(models.Model):
    """Store transaction information from QuickBooks via Unified.to"""
    TRANSACTION_TYPE_CHOICES = [
        ('PAYMENT', 'Payment'),
        ('REFUND', 'Refund'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('DEPOSIT', 'Deposit'),
        ('OTHER', 'Other'),
    ]
    
    # Unified.to fields
    external_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Links to customer (from contacts array)
    contact_id = models.CharField(max_length=255, db_index=True, blank=True, null=True)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        related_name='transactions',
        null=True,
        blank=True
    )
    
    # Transaction details
    memo = models.TextField(blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    account_id = models.CharField(max_length=255, blank=True, null=True)
    
    transaction_type = models.CharField(
        max_length=20, 
        choices=TRANSACTION_TYPE_CHOICES, 
        default='OTHER'
    )
    
    # Metadata
    external_created_at = models.DateTimeField(blank=True, null=True)
    external_updated_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    raw_data = models.JSONField(blank=True, null=True)
    
    class Meta:
        db_table = 'ar_dashboard_transaction'
        ordering = ['-external_created_at']
    
    def __str__(self):
        customer_name = self.customer.name if self.customer else self.contact_id
        return f"Transaction {self.total_amount} - {customer_name}"


class ARAgingSummary(models.Model):
    """Pre-calculated AR Aging summary for fast dashboard queries"""
    customer = models.OneToOneField(
        Customer, 
        on_delete=models.CASCADE, 
        related_name='aging_summary'
    )
    
    # Aging buckets (in dollars)
    current = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_1_30 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_31_60 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_61_90 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_91_120 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    days_120_plus = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Totals
    total_outstanding = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_overdue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Invoice counts
    total_invoices = models.IntegerField(default=0)
    overdue_invoices = models.IntegerField(default=0)
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ar_dashboard_aragingsummary'
        ordering = ['-total_outstanding']
    
    def __str__(self):
        return f"AR Summary - {self.customer.name}: ${self.total_outstanding}"
    
    @property
    def percent_overdue(self):
        """Calculate percentage of AR that is overdue"""
        if self.total_outstanding > 0:
            return round((self.total_overdue / self.total_outstanding) * 100, 2)
        return 0
    
    @property
    def average_days_overdue(self):
        """Calculate average days overdue for this customer"""
        if self.overdue_invoices > 0:
            # This would need to be calculated from actual invoices
            # For now, return a placeholder
            return 0
        return 0
    
    