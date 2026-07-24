"""
Dashboard routes.
"""
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.database import get_db
from app.utils.helpers import query_one, query_all

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def dashboard():
    """Main dashboard view with professional statistics."""
    conn = get_db()

    # Basic counts
    total_keluar = query_one(conn,
        "SELECT COUNT(*) AS c FROM surat_izin WHERE jenis='keluar'")['c']
    total_masuk = query_one(conn,
        "SELECT COUNT(*) AS c FROM surat_izin WHERE jenis='masuk'")['c']
    total_pending = query_one(conn,
        "SELECT COUNT(*) AS c FROM surat_izin WHERE status='pending'")['c']
    total_review = query_one(conn,
        "SELECT COUNT(*) AS c FROM surat_izin WHERE status='review'")['c']
    total_approved = query_one(conn,
        "SELECT COUNT(*) AS c FROM surat_izin WHERE status='approved'")['c']
    total_rejected = query_one(conn,
        "SELECT COUNT(*) AS c FROM surat_izin WHERE status='rejected'")['c']

    # Pending approvals for current user
    pending_approvals = []
    if current_user.role in ('user', 'pemberi_kerja', 'admin'):
        pending_approvals = query_all(conn, """
            SELECT id, no_surat, jenis, nama, created_at
            FROM surat_izin
            WHERE approval_user = 'pending'
            ORDER BY created_at ASC LIMIT 5
        """)
    elif current_user.role in ('satpam', 'admin'):
        pending_approvals = query_all(conn, """
            SELECT id, no_surat, jenis, nama, created_at
            FROM surat_izin
            WHERE approval_user IN ('sesuai', 'tidak_sesuai')
              AND approval_satpam = 'pending'
            ORDER BY created_at ASC LIMIT 5
        """)
    elif current_user.role in ('asman', 'admin'):
        pending_approvals = query_all(conn, """
            SELECT id, no_surat, jenis, nama, created_at
            FROM surat_izin
            WHERE approval_satpam = 'sesuai'
              AND approval_asman = 'pending'
            ORDER BY created_at ASC LIMIT 5
        """)
    elif current_user.role in ('manager', 'admin'):
        pending_approvals = query_all(conn, """
            SELECT id, no_surat, jenis, nama, created_at
            FROM surat_izin
            WHERE approval_asman IN ('approved', 'rejected')
              AND approval_manager = 'pending'
            ORDER BY created_at ASC LIMIT 5
        """)

    # Recent surat
    recent = query_all(conn,
        "SELECT * FROM surat_izin ORDER BY created_at DESC LIMIT 10")

    # Monthly trend (last 6 months)
    monthly = query_all(conn, """
        SELECT DATE_FORMAT(tanggal, '%%Y-%%m') AS bulan,
               SUM(CASE WHEN jenis='keluar' THEN 1 ELSE 0 END) AS keluar,
               SUM(CASE WHEN jenis='masuk' THEN 1 ELSE 0 END) AS masuk
        FROM surat_izin
        GROUP BY bulan ORDER BY bulan DESC LIMIT 6
    """)

    # Divisi statistics
    divisi_stats = query_all(conn, """
        SELECT divisi, COUNT(*) AS total FROM surat_izin GROUP BY divisi ORDER BY total DESC
    """)

    # Overdue count
    overdue_count = query_one(conn, """
        SELECT COUNT(*) AS c FROM surat_izin
        WHERE status IN ('pending', 'review')
          AND created_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)
    """)['c']

    # My submissions
    my_submissions = query_all(conn, """
        SELECT * FROM surat_izin
        WHERE created_by = %s
        ORDER BY created_at DESC LIMIT 5
    """, (current_user.id,))

    conn.close()

    return render_template('dashboard.html',
                           total_keluar=total_keluar,
                           total_masuk=total_masuk,
                           total_pending=total_pending,
                           total_review=total_review,
                           total_approved=total_approved,
                           total_rejected=total_rejected,
                           pending_approvals=pending_approvals,
                           recent=recent,
                           monthly=list(reversed(monthly)),
                           divisi_stats=divisi_stats,
                           overdue_count=overdue_count,
                           my_submissions=my_submissions)
