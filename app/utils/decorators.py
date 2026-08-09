from functools import wraps
from flask import g

class AuthorizationError(Exception):
    def __init__(self, message="Access Denied", status_code=403):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, "user") or g.user is None:
                raise AuthorizationError("Authentication Required", 401)
            
            user_roles = g.user.get("roles", [])
            if not any(role in user_roles for role in roles):
                raise AuthorizationError("Access Denied - Insufficient Permissions", 403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def permission_required(perm_name: str):
    """Decorator לאכיפת הרשאות גנריות (RBAC) מרוכזות."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, "user") or g.user is None:
                raise AuthorizationError("Authentication Required", 401)
            
            user_perms = g.user.get("permissions", [])
            if perm_name not in user_perms:
                raise AuthorizationError(f"Access Denied - Missing Permission: {perm_name}", 403)
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
