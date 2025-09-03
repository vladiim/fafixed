from django.db import models
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
