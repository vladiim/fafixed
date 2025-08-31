from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from .models import UserProfile, Account

def clear_user_context(request):
    """
    Helper to clear all user-related session data and context
    """
    # Clear session data
    if 'current_account_id' in request.session:
        del request.session['current_account_id']
    
    # Clear any other session keys that might be user-specific
    keys_to_clear = [key for key in request.session.keys() if key.startswith('user_') or key.startswith('account_')]
    for key in keys_to_clear:
        del request.session[key]
    
    request.session.modified = True

def current_user_and_account(request):
    """
    Context processor to provide current_user and current_account in templates
    """
    context = {
        'current_user': None,
        'current_account': None,
        'WEBSOCKET_URL': settings.WEBSOCKET_URL,  # Add WebSocket URL to context
    }
    
    # If user is anonymous or not authenticated, clear any stale context
    if not request.user or isinstance(request.user, AnonymousUser) or not request.user.is_authenticated:
        clear_user_context(request)
        return context
    
    context['current_user'] = request.user
    
    # Get or create user profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Get current account from session or profile
    current_account_id = request.session.get('current_account_id')
    current_account = None
    
    if current_account_id:
        try:
            current_account = Account.objects.get(pk=current_account_id)
            # Verify user has access to this account
            if not current_account.account_users.filter(user=request.user).exists():
                current_account = None
                del request.session['current_account_id']
        except Account.DoesNotExist:
            del request.session['current_account_id']
    
    # If no current account in session, get from profile or default to first account
    if not current_account:
        if profile.current_account and profile.current_account.account_users.filter(user=request.user).exists():
            current_account = profile.current_account
        else:
            # Default to first account user has access to
            account_membership = request.user.account_memberships.first()
            if account_membership:
                current_account = account_membership.account
                # Update profile
                profile.current_account = current_account
                profile.save()
    
    context['current_account'] = current_account
    
    # Store in session for next request
    if current_account:
        request.session['current_account_id'] = current_account.pk
    
    return context