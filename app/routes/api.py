"""
API routes.
REST API endpoints for surat and stats.
"""
import json
from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user

from app.database import get_db
from app.utils.helpers import query_all, query_one

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/surat/<int:id>')
@login_required
def get_surat(id):
    """
    Get a single surat by ID.
    Access control: Users can only see their own surat,
    or staff roles (admin, satpam, asman, manager) can see all.
    """
    conn = get_db()
    s = query_one(conn, "SELECT * FROM surat_izin WHERE id=%s", (id,))
    conn.close()

    if not s:
        return jsonify(success=False, error='Tidak ditemukan'), 404

    # Access control: Allow if user created this surat OR has elevated role
    can_access = (
        s['created_by'] == current_user.id or
        current_user.role in ('admin', 'satpam', 'asman', 'manager')
    )

    if not can_access:
        return jsonify(success=False, error='Anda tidak memiliki akses ke surat ini'), 403

    d = dict(s)
    d['barang_items'] = json.loads(d['barang_items'])
    d['tanggal'] = str(d['tanggal'])
    d['tgl_terbit'] = str(d['tgl_terbit'])
    d['created_at'] = str(d['created_at']) if d['created_at'] else None
    d['updated_at'] = str(d['updated_at']) if d['updated_at'] else None
    return jsonify(success=True, data=d)


@api_bp.route('/api/stats')
@login_required
def get_stats():
    """
    Get monthly statistics for charts.
    Access control: All authenticated users can view statistics.
    """
    conn = get_db()
    monthly = query_all(conn, """
        SELECT DATE_FORMAT(tanggal, '%%Y-%%m') AS bulan,
               SUM(CASE WHEN jenis='keluar' THEN 1 ELSE 0 END) AS keluar,
               SUM(CASE WHEN jenis='masuk' THEN 1 ELSE 0 END) AS masuk
        FROM surat_izin GROUP BY bulan ORDER BY bulan DESC LIMIT 12
    """)
    conn.close()
    return jsonify(monthly)
