from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from turbo_helper import turbo_stream
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from integrations.models import TransactionData, Integration, TransactionValidationStatus
from integrations.forms import TransactionEditForm
from core.decorators import check_user_can_edit_transactions
from financial_data.models import SalesInvoice, Contact
import logging


@login_required
def transaction_list(request, integration_prefix_id):
    """Display paginated list of transactions for an integration"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Transaction list view called for integration {integration_prefix_id} by user {request.user.email}")
    
    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            status='active'
        )
        
        # Get transactions for this integration, ordered by date (newest first)
        transactions = TransactionData.objects.filter(
            integration=integration
        ).prefetch_related('line_items').order_by('-date', '-created_at')
        
        # Pagination
        paginator = Paginator(transactions, 25)  # Show 25 transactions per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'integration': integration,
            'page_obj': page_obj,
            'total_transactions': transactions.count(),
        }
        
        logger.info(f"Rendering transaction list with {transactions.count()} total transactions, showing page {page_obj.number} of {paginator.num_pages}")
        return render(request, 'integrations/transaction_list.html', context)
        
    except Exception as e:
        logger.error(f"Failed to load transaction list for integration {integration_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to load transactions: {str(e)}")
        return redirect('dashboard')


@login_required
def transaction_actions(request, transaction_prefix_id):
    """Get current transaction actions state (for Turbo Frame reloads)"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Loading transaction actions for transaction {transaction_prefix_id}")
    
    try:
        # First check if transaction exists at all
        try:
            transaction = TransactionData.objects.get(prefix_id=transaction_prefix_id)
        except TransactionData.DoesNotExist:
            return JsonResponse({'error': 'Transaction not found'}, status=404)
        
        # Then check if user has access to this transaction
        if not transaction.integration.account.account_users.filter(user=request.user).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Check if there are any pending validation statuses (indicating a task is running)
        pending_statuses = transaction.validation_statuses.filter(status='pending')
        task_id = None
        if pending_statuses.exists():
            # Simulate task_id for UI (we don't track actual celery task IDs in the DB)
            # In a real implementation, you might store the task_id in the TransactionValidationStatus
            task_id = "running"  # Just indicate that tasks are running
        
        # Return Turbo Frame with current state
        return render(request, 'financial_data/partials/transaction_actions.html', {
            'transaction': transaction,
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"Error fetching transaction actions for transaction {transaction_prefix_id}: {str(e)}", exc_info=True)
        
        return render(request, 'financial_data/partials/transaction_actions.html', {
            'transaction': transaction if 'transaction' in locals() else None,
            'error': f'Failed to load transaction actions: {str(e)}'
        }, status=500)


@login_required
def refresh_transaction_status(request, transaction_prefix_id):
    """Refresh transaction validation status with Turbo Stream response"""
    logger = logging.getLogger(__name__)
    
    try:
        transaction = get_object_or_404(
            TransactionData,
            prefix_id=transaction_prefix_id
        )
        
        # Check user access
        if not transaction.integration.account.account_users.filter(user=request.user).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get latest validation statuses
        validation_statuses = transaction.validation_statuses.order_by('-updated_at')
        
        context = {
            'transaction': transaction,
            'validation_statuses': validation_statuses,
        }
        
        # Return Turbo Stream response to update status
        return turbo_stream.turbo_stream(
            turbo_stream.replace(
                f"transaction-{transaction.prefix_id}-status",
                render(request, 'financial_data/partials/transaction_status.html', context).content.decode()
            ),
            content_type="text/vnd.turbo-stream.html"
        )
        
    except Exception as e:
        logger.error(f"Error refreshing transaction status: {str(e)}", exc_info=True)
        # Return error in Turbo Stream format
        return turbo_stream.turbo_stream(
            turbo_stream.replace(
                f"transaction-{transaction_prefix_id}-status",
                f"<div class='text-red-500'>Error: {str(e)}</div>"
            ),
            content_type="text/vnd.turbo-stream.html"
        )


@login_required
def transaction_edit(request, transaction_prefix_id):
    """Edit a transaction"""
    logger = logging.getLogger(__name__)
    
    # Check user permissions
    if not check_user_can_edit_transactions(request.user):
        messages.warning(request, "Access denied. Only super administrators can edit transactions.")
        return redirect('dashboard')
    
    try:
        transaction = get_object_or_404(
            TransactionData,
            prefix_id=transaction_prefix_id
        )
        
        # Check user access to this transaction's integration
        if not transaction.integration.account.account_users.filter(user=request.user).exists():
            messages.error(request, "Access denied")
            return redirect('dashboard')
        
        if request.method == 'POST':
            form = TransactionEditForm(request.POST, instance=transaction)
            if form.is_valid():
                form.save()
                messages.success(request, "Transaction updated successfully")
                return redirect('transaction_list', integration_prefix_id=transaction.integration.prefix_id)
            else:
                logger.error(f"Form errors: {form.errors}")
                messages.error(request, "Please correct the errors below")
        else:
            form = TransactionEditForm(instance=transaction)
        
        context = {
            'form': form,
            'transaction': transaction,
            'integration': transaction.integration,
        }
        
        return render(request, 'financial_data/transaction_edit.html', context)
        
    except Exception as e:
        logger.error(f"Error editing transaction {transaction_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to edit transaction: {str(e)}")
        return redirect('dashboard')


@login_required
def transaction_edit_check(request, transaction_prefix_id):
    """Check if user can edit transaction and redirect appropriately"""
    
    # Check user permissions
    if not check_user_can_edit_transactions(request.user):
        messages.warning(request, "Access denied. Only super administrators can edit transactions.")
        return redirect('dashboard')
    
    # Redirect to actual edit view
    return redirect('transaction_edit', transaction_prefix_id=transaction_prefix_id)


@login_required
def xero_chart_accounts(request, integration_prefix_id):
    """Display Xero Chart of Accounts for selection (bank accounts, revenue accounts, etc.)"""
    logger = logging.getLogger(__name__)
    
    logger.info(f"Xero chart accounts view called for integration {integration_prefix_id} by user {request.user.email}")
    
    try:
        integration = get_object_or_404(
            Integration, 
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            provider__name='xero'
        )
        
        logger.info(f"Found integration: {integration.id} - {integration.organization_name} (Status: {integration.status})")
        
        # Check if integration has completed OAuth (has credentials)
        if not hasattr(integration, 'credentials'):
            logger.error(f"Integration {integration.id} has no credentials")
            messages.error(request, "Integration not properly connected. Please reconnect to Xero.")
            return redirect('dashboard')
        
        # Get the service for this integration
        from integrations.services.base import IntegrationServiceRegistry
        logger.info("Getting integration service...")
        service = IntegrationServiceRegistry.get_service(integration)
        logger.info(f"Got service: {service.__class__.__name__}")
        
        # Fetch client organizations from Xero
        logger.info("Fetching client organizations from Xero API...")
        try:
            organizations = service.get_organizations()
            logger.info(f"Successfully fetched {len(organizations)} client organizations from Xero")
            
            context = {
                'integration': integration,
                'organizations': organizations,
            }
            
            return render(request, 'financial_data/xero_chart_accounts.html', context)
            
        except Exception as api_error:
            logger.error(f"Failed to fetch organizations from Xero: {str(api_error)}", exc_info=True)
            messages.error(request, f"Failed to load chart of accounts: {str(api_error)}")
            return redirect('dashboard')
        
    except Exception as e:
        logger.error(f"Error in xero_chart_accounts view: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to load chart of accounts: {str(e)}")
        return redirect('dashboard')


@login_required
def import_chart_accounts(request, integration_prefix_id):
    """Import chart of accounts and start initial sync"""
    logger = logging.getLogger(__name__)
    
    if request.method != 'POST':
        return redirect('xero_chart_accounts', integration_prefix_id=integration_prefix_id)
    
    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            provider__name='xero'
        )
        
        selected_org_id = request.POST.get('selected_organization')
        if not selected_org_id:
            messages.error(request, "No organization selected")
            return redirect('xero_chart_accounts', integration_prefix_id=integration_prefix_id)
        
        # Update integration with selected organization
        integration.external_account_id = selected_org_id
        integration.save()
        
        # Start initial sync
        from integrations.services.base import IntegrationServiceRegistry
        service = IntegrationServiceRegistry.get_service(integration)
        
        result = service.sync_transactions_async()
        
        if result.get('success'):
            messages.success(request, "Chart of accounts imported successfully. Data sync started.")
        else:
            messages.error(request, f"Failed to start sync: {result.get('error')}")
        
        return redirect('transaction_list', integration_prefix_id=integration_prefix_id)
        
    except Exception as e:
        logger.error(f"Error importing chart accounts: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to import chart of accounts: {str(e)}")
        return redirect('dashboard')


@login_required
def invoice_list(request, integration_prefix_id):
    """Display paginated list of sales invoices for an integration"""
    logger = logging.getLogger(__name__)

    logger.info(f"Invoice list view called for integration {integration_prefix_id} by user {request.user.email}")

    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            status='active'
        )

        # Base queryset for invoices
        invoices = SalesInvoice.objects.filter(
            integration=integration
        ).select_related('contact').prefetch_related('line_items', 'payments')

        # Filter by status
        status_filter = request.GET.get('status')
        if status_filter:
            invoices = invoices.filter(status=status_filter)

        # Filter by overdue
        show_overdue = request.GET.get('overdue')
        if show_overdue == 'true':
            from datetime import date
            invoices = invoices.filter(
                due_date__lt=date.today(),
                amount_due__gt=0
            ).exclude(Q(status='PAID') | Q(status='VOIDED') | Q(status='DELETED'))

        # Search by invoice number or contact name
        search_query = request.GET.get('q')
        if search_query:
            invoices = invoices.filter(
                Q(invoice_number__icontains=search_query) |
                Q(contact__name__icontains=search_query)
            )

        # Order by date (newest first)
        invoices = invoices.order_by('-invoice_date', '-created_at')

        # Calculate summary statistics
        summary = {
            'total_count': invoices.count(),
            'total_amount': invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'total_due': invoices.aggregate(Sum('amount_due'))['amount_due__sum'] or 0,
        }

        # Pagination
        paginator = Paginator(invoices, 25)  # Show 25 invoices per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Get unique statuses for filter dropdown
        available_statuses = SalesInvoice.objects.filter(
            integration=integration
        ).values_list('status', flat=True).distinct()

        context = {
            'integration': integration,
            'page_obj': page_obj,
            'summary': summary,
            'available_statuses': available_statuses,
            'status_filter': status_filter,
            'show_overdue': show_overdue,
            'search_query': search_query,
        }

        logger.info(f"Rendering invoice list with {summary['total_count']} total invoices, showing page {page_obj.number} of {paginator.num_pages}")
        return render(request, 'financial_data/invoice_list.html', context)

    except Exception as e:
        logger.error(f"Failed to load invoice list for integration {integration_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to load invoices: {str(e)}")
        return redirect('dashboard')


@login_required
def invoice_detail(request, invoice_prefix_id):
    """Display detailed view of a single invoice with line items and payments"""
    logger = logging.getLogger(__name__)

    logger.info(f"Invoice detail view called for invoice {invoice_prefix_id} by user {request.user.email}")

    try:
        invoice = get_object_or_404(
            SalesInvoice.objects.select_related('integration', 'contact', 'account')
                                .prefetch_related('line_items', 'payments', 'payments__transaction'),
            prefix_id=invoice_prefix_id,
            account__account_users__user=request.user
        )

        # Calculate payment totals
        total_payments = sum(payment.payment_amount for payment in invoice.payments.all())

        # Get related transactions (reconciled payments)
        reconciled_payments = invoice.payments.filter(status='MATCHED').select_related('transaction')

        context = {
            'invoice': invoice,
            'integration': invoice.integration,
            'total_payments': total_payments,
            'reconciled_payments': reconciled_payments,
        }

        logger.info(f"Rendering invoice detail for {invoice.invoice_number} with {invoice.line_items.count()} line items and {invoice.payments.count()} payments")
        return render(request, 'financial_data/invoice_detail.html', context)

    except Exception as e:
        logger.error(f"Failed to load invoice detail for {invoice_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to load invoice: {str(e)}")
        return redirect('dashboard')


@login_required
def reconciliation_dashboard(request, integration_prefix_id):
    """Display payment reconciliation dashboard with unreconciled transactions and matches"""
    logger = logging.getLogger(__name__)

    logger.info(f"Reconciliation dashboard view called for integration {integration_prefix_id} by user {request.user.email}")

    try:
        integration = get_object_or_404(
            Integration,
            prefix_id=integration_prefix_id,
            account__account_users__user=request.user,
            status='active'
        )

        # Get connection for this integration
        from connections.models import Connection
        from financial_data.models import Transaction, InvoicePayment
        from financial_data.services.accounting_repository import AccountingRepository
        from financial_data.services.payment_reconciler import PaymentReconciler

        try:
            connection = Connection.objects.get(
                external_account_id=integration.external_account_id,
                account=integration.account
            )
        except Connection.DoesNotExist:
            messages.warning(request, "No bank connection found for this integration")
            return redirect('dashboard')

        # Get unreconciled transactions (incoming payments only)
        unreconciled_transactions = Transaction.objects.filter(
            connection=connection,
            is_reconciled=False,
            transaction_type='receive'
        ).order_by('-date')[:50]  # Show last 50

        # Initialize reconciler
        repository = AccountingRepository(integration)
        reconciler = PaymentReconciler(repository)

        # Find matches for each transaction
        transactions_with_matches = []
        for transaction in unreconciled_transactions:
            matches = reconciler.find_invoice_matches(transaction)
            transactions_with_matches.append({
                'transaction': transaction,
                'matches': matches[:3],  # Show top 3 matches
                'best_match': matches[0] if matches else None,
                'can_auto_reconcile': matches[0].confidence >= reconciler.AUTO_RECONCILE_THRESHOLD if matches else False
            })

        # Get recent reconciliations
        recent_reconciliations = InvoicePayment.objects.filter(
            integration=integration,
            status='MATCHED'
        ).select_related('invoice', 'transaction', 'reconciled_by').order_by('-created_at')[:20]

        # Summary stats
        total_unreconciled = Transaction.objects.filter(
            connection=connection,
            is_reconciled=False,
            transaction_type='receive'
        ).count()

        total_unreconciled_amount = Transaction.objects.filter(
            connection=connection,
            is_reconciled=False,
            transaction_type='receive'
        ).aggregate(Sum('amount'))['amount__sum'] or 0

        context = {
            'integration': integration,
            'transactions_with_matches': transactions_with_matches,
            'recent_reconciliations': recent_reconciliations,
            'total_unreconciled': total_unreconciled,
            'total_unreconciled_amount': total_unreconciled_amount,
        }

        logger.info(f"Rendering reconciliation dashboard with {len(transactions_with_matches)} unreconciled transactions")
        return render(request, 'financial_data/reconciliation_dashboard.html', context)

    except Exception as e:
        logger.error(f"Failed to load reconciliation dashboard for integration {integration_prefix_id}: {str(e)}", exc_info=True)
        messages.error(request, f"Failed to load reconciliation dashboard: {str(e)}")
        return redirect('dashboard')
