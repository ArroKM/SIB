"""
User model.
"""
from flask_login import UserMixin

from app.extensions import login_manager


class User(UserMixin):
    """User model for authentication and authorization."""

    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.nama_lengkap = row['nama_lengkap']
        self.role = row['role']
        self.divisi = row.get('divisi', '')
        self.is_active_user = row.get('is_active', 1)
        # Note: is_active check is performed in user_loader

    def get_id(self):
        """Return the unique identifier of the user (required by Flask-Login)."""
        return str(self.id)

    def is_active(self):
        """
        Required by Flask-Login to check if user account is active.
        Returns True only for active users.
        Note: Inactive users are already filtered in user_loader, so this always returns True.
        """
        return self.is_active_user == 1

    def is_admin(self):
        """Check if user has admin role."""
        return self.role == 'admin'

    def is_manager(self):
        """Check if user has manager role."""
        return self.role == 'manager'

    def is_satpam(self):
        """Check if user has satpam (security) role."""
        return self.role == 'satpam'

    def is_asman(self):
        """Check if user has asman (assistant manager) role."""
        return self.role == 'asman'

    def is_staff(self):
        """Check if user has staff role."""
        return self.role == 'staff'

    def is_user(self):
        """Check if user has regular user role."""
        return self.role == 'user'

    def has_role(self, *roles):
        """Check if user has any of the specified roles."""
        return self.role in roles

    def is_pemberi_kerja(self):
        """Check if user has pemberi_kerja (PIC Vendor) role."""
        return self.role == 'pemberi_kerja'

    def can_approve_user(self):
        """Check if user can perform User/Pemberi Kerja approval."""
        return self.role in ('user', 'admin', 'pemberi_kerja')

    def can_approve_satpam(self):
        """Check if user can perform Satpam approval."""
        return self.role in ('satpam', 'admin')

    def can_approve_asman(self):
        """Check if user can perform Asman review."""
        return self.role in ('asman', 'admin')

    def can_approve_manager(self):
        """Check if user can perform Manager approval."""
        return self.role in ('manager', 'admin')

    def can_approve_any(self):
        """Check if user can approve at any stage."""
        return self.role in ('admin', 'user', 'satpam', 'asman', 'manager', 'pemberi_kerja')

    def can_delegate(self):
        """Check if user can delegate their approval authority."""
        return self.role in ('manager', 'asman', 'admin')

    def can_manage_settings(self):
        """Check if user can manage system settings."""
        return self.role == 'admin'

    def can_view_api(self):
        """Check if user can access API endpoints."""
        return self.role == 'admin'

    def can_escalate(self):
        """Check if user can escalate approvals."""
        return self.role in ('admin', 'manager')

    def can_manage_users(self):
        """Check if user can manage other users."""
        return self.role == 'admin'

    def can_delete_surat(self):
        """Check if user can delete surat."""
        return self.role in ('admin', 'manager')

    def can_view_activity_log(self):
        """Check if user can view activity log."""
        return self.role == 'admin'


@login_manager.user_loader
def load_user(uid):
    """Load user by ID for Flask-Login."""
    from app.database import get_db
    from app.utils.helpers import query_one

    try:
        conn = get_db()
        row = query_one(conn, "SELECT * FROM users WHERE id=%s AND is_active=1", (uid,))
        conn.close()
        return User(row) if row else None
    except Exception:
        return None
