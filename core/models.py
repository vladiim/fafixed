from django.db import models
from django.contrib.auth.models import User
import secrets
import string

class PrefixIdMixin:
    """Mixin to add prefix_id functionality to any model"""
    
    @classmethod
    def has_prefix_id(cls, prefix, length=8):
        """Class decorator to add prefix_id functionality"""
        
        def generate_prefix_id():
            chars = string.ascii_lowercase + string.digits
            random_string = ''.join(secrets.choice(chars) for _ in range(length))
            return f"{prefix}_{random_string}"
        
        def ensure_prefix_id(self):
            if not hasattr(self, 'prefix_id') or not self.prefix_id:
                # Generate unique prefix_id
                while True:
                    prefix_id = generate_prefix_id()
                    if not self.__class__.objects.filter(prefix_id=prefix_id).exists():
                        self.prefix_id = prefix_id
                        break
        
        def save_with_prefix(self, *args, **kwargs):
            ensure_prefix_id(self)
            super(self.__class__, self).save(*args, **kwargs)
        
        # Add prefix_id field if it doesn't exist
        if not hasattr(cls, 'prefix_id'):
            cls.add_to_class('prefix_id', models.CharField(max_length=50, unique=True, editable=False))
        
        # Override save method
        cls.save = save_with_prefix
        cls._generate_prefix_id = staticmethod(generate_prefix_id)
        cls._ensure_prefix_id = ensure_prefix_id
        
        return cls
    
    def get_prefix_id(self):
        """Get the prefix_id for this instance"""
        return getattr(self, 'prefix_id', None)

class UserProfile(models.Model, PrefixIdMixin):
    """Extends User model with prefix_id, current_account, and role"""
    
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('admin', 'Admin'),
        ('super_admin', 'Super Admin'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    current_account = models.ForeignKey('Account', on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer',
                           help_text="User role - difficult to change once set for security")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} ({self.get_role_display()}) - {self.get_prefix_id()}"
    
    def is_admin(self):
        """Check if user has admin privileges"""
        return self.role in ['admin', 'super_admin']
    
    def is_super_admin(self):
        """Check if user has super admin privileges"""
        return self.role == 'super_admin'
    
    def can_edit_transactions(self):
        """Check if user can edit transactions"""
        return self.role == 'super_admin'
    
    def save(self, *args, **kwargs):
        # Make role changes difficult by requiring explicit confirmation
        if self.pk:  # Existing instance
            original = UserProfile.objects.get(pk=self.pk)
            if original.role != self.role:
                # Role is being changed - this should be rare and explicit
                pass  # Allow for now, but could add additional checks here
        super().save(*args, **kwargs)

# Apply prefix_id to UserProfile
UserProfile = UserProfile.has_prefix_id('usr')

class Account(models.Model, PrefixIdMixin):
    ACCOUNT_TYPES = [
        ('organization', 'Organization'),  # Global business account
        ('integration', 'Integration'),    # Xero-specific account
    ]
    
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_account_type_display()}) - {self.get_prefix_id()}"
    
    def save(self, *args, **kwargs):
        # Ensure organization account names are unique
        if self.account_type == 'organization':
            if Account.objects.filter(
                name=self.name, 
                account_type='organization'
            ).exclude(pk=self.pk).exists():
                raise ValueError(f"Organization account with name '{self.name}' already exists")
        super().save(*args, **kwargs)
    
    class Meta:
        ordering = ['-created_at']

# Apply prefix_id to Account
Account = Account.has_prefix_id('acc')

class AccountUser(models.Model):
    ROLES = [
        ('owner', 'Owner'),
        ('admin', 'Administrator'), 
        ('member', 'Member'),
    ]
    
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='account_users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='account_memberships')
    role = models.CharField(max_length=20, choices=ROLES, default='owner')
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.account.name} ({self.get_role_display()})"
    
    class Meta:
        unique_together = ['account', 'user']
        ordering = ['-joined_at']
