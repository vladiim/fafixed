"""
Role-based access control decorators for user permissions.
"""

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from functools import wraps


def role_required(*allowed_roles):
    """
    Decorator to require specific user roles.
    
    Args:
        *allowed_roles: List of role strings that are allowed access
        
    Usage:
        @role_required('admin', 'super_admin')
        def admin_only_view(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            # Check if user has profile
            if not hasattr(request.user, 'profile'):
                messages.error(request, "User profile not found. Please contact support.")
                return redirect('dashboard')
            
            # Check if user role is in allowed roles
            user_role = request.user.profile.role
            if user_role not in allowed_roles:
                messages.warning(request, "Access denied. Insufficient privileges.")
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def super_admin_required(view_func):
    """
    Decorator to require super_admin role.
    
    Usage:
        @super_admin_required
        def super_admin_only_view(request):
            pass
    """
    return role_required('super_admin')(view_func)


def admin_required(view_func):
    """
    Decorator to require admin or super_admin role.
    
    Usage:
        @admin_required  
        def admin_view(request):
            pass
    """
    return role_required('admin', 'super_admin')(view_func)


def check_user_can_edit_transactions(user):
    """
    Check if user can edit transactions (super_admin only).
    
    Args:
        user: Django User instance
        
    Returns:
        bool: True if user can edit transactions
    """
    if not hasattr(user, 'profile'):
        return False
    return user.profile.can_edit_transactions()


class RoleRequiredMixin:
    """
    Mixin for class-based views to require specific roles.
    
    Usage:
        class MyView(RoleRequiredMixin, View):
            required_roles = ['admin', 'super_admin']
    """
    required_roles = []
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check if user has profile
        if not hasattr(request.user, 'profile'):
            messages.error(request, "User profile not found. Please contact support.")
            return redirect('dashboard')
        
        # Check if user role is in required roles
        user_role = request.user.profile.role
        if self.required_roles and user_role not in self.required_roles:
            messages.warning(request, "Access denied. Insufficient privileges.")
            return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)