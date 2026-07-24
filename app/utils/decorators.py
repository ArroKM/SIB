"""
Decorators for routes.
"""
from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*roles):
    """
    Decorator to restrict access to users with specific roles.

    Usage:
        @role_required('admin', 'manager')
        def admin_only():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if current_user.role not in roles:
                abort(403)
            return f(*a, **kw)
        return wrapper
    return decorator
