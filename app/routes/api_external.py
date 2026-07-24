"""
External API routes for third-party integration.
Requires API key authentication.
"""
import json
import secrets
from datetime import datetime

from flask import Blueprint, request, jsonify, abort
from flask_login import login_required

from app.database import get_db
from app.utils.helpers import query_one, query_all, execute
from app.config import Config

api_external_bp = Blueprint('api_external', __name__, url_prefix='/api/v1')


def require_api_key(f):
    """Decorator to require valid API key."""
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-KEY')

        if not api_key:
            abort(401, description='API key required')

        conn = get_db()
        key_row = query_one(conn, """
            SELECT * FROM api_keys
            WHERE api_key = %s AND is_active = 1
        """, (api_key,))

        if not key_row:
            conn.close()
            abort(401, description='Invalid API key')

        # Update last used
        execute(conn, "UPDATE api_keys SET last_used_at = NOW() WHERE id = %s", (key_row['id'],))
        conn.close()

        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated


# ---------------------------------------------------------------------------
# API Keys Management (Admin only)
# ---------------------------------------------------------------------------

@api_external_bp.route('/keys', methods=['GET'])
@login_required
def list_api_keys():
    """List all API keys (admin only)."""
    if not hasattr(request, 'current_user') or request.current_user.role != 'admin':
        # Check via session
        from flask_login import current_user
        if current_user.role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db()
    keys = query_all(conn, """
        SELECT id, client_name, description, is_active, last_used_at, created_at
        FROM api_keys ORDER BY created_at DESC
    """)
    conn.close()

    return jsonify({'success': True, 'keys': keys})


@api_external_bp.route('/keys', methods=['POST'])
@login_required
def create_api_key():
    """Create new API key (admin only)."""
    from flask_login import current_user
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    client_name = data.get('client_name')
    description = data.get('description', '')
    permissions = data.get('permissions', [])

    if not client_name:
        return jsonify({'error': 'Client name required'}), 400

    # Generate secure API key
    api_key = secrets.token_hex(32)

    conn = get_db()
    sid = execute(conn, """
        INSERT INTO api_keys (api_key, client_name, description, permissions, created_by)
        VALUES (%s, %s, %s, %s, %s)
    """, (api_key, client_name, description, json.dumps(permissions), current_user.id))
    conn.close()

    return jsonify({
        'success': True,
        'api_key': api_key,
        'id': sid,
        'message': 'API key created. Store it securely - it will not be shown again.'
    })


@api_external_bp.route('/keys/<int:key_id>', methods=['DELETE'])
@login_required
def revoke_api_key(key_id):
    """Revoke an API key (admin only)."""
    from flask_login import current_user
    if current_user.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    conn = get_db()
    execute(conn, "UPDATE api_keys SET is_active = 0 WHERE id = %s", (key_id,))
    conn.close()

    return jsonify({'success': True, 'message': 'API key revoked'})


# ---------------------------------------------------------------------------
# External Surat Endpoints
# ---------------------------------------------------------------------------

@api_external_bp.route('/surat')
@require_api_key
def get_surat_list():
    """
    Get list of surat with optional filters.
    Query params: jenis, status, tanggal_start, tanggal_end, page, limit
    """
    jenis = request.args.get('jenis')
    status = request.args.get('status')
    tanggal_start = request.args.get('tanggal_start')
    tanggal_end = request.args.get('tanggal_end')
    page = int(request.args.get('page', 1))
    limit = min(int(request.args.get('limit', 20)), 100)

    # Validate pagination parameters
    if page < 1:
        page = 1
    if limit < 1:
        limit = 20
    if limit > 100:
        limit = 100

    conn = get_db()

    query = "SELECT * FROM surat_izin WHERE 1=1"
    params = []

    if jenis:
        query += " AND jenis = %s"
        params.append(jenis)
    if status:
        query += " AND status = %s"
        params.append(status)
    if tanggal_start:
        query += " AND tanggal >= %s"
        params.append(tanggal_start)
    if tanggal_end:
        query += " AND tanggal <= %s"
        params.append(tanggal_end)

    # Count total
    count_query = query.replace("SELECT *", "SELECT COUNT(*) as total")
    total = query_one(conn, count_query, params)['total']

    # Add pagination using parameterized query for limit and offset
    offset = (page - 1) * limit
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    rows = query_all(conn, query, params)
    conn.close()

    return jsonify({
        'success': True,
        'data': rows,
        'pagination': {
            'page': page,
            'limit': limit,
            'total': total,
            'pages': (total + limit - 1) // limit if limit > 0 else 0
        }
    })


@api_external_bp.route('/surat/<int:surat_id>')
@require_api_key
def get_surat_detail(surat_id):
    """Get detail of a specific surat."""
    conn = get_db()
    surat = query_one(conn, "SELECT * FROM surat_izin WHERE id = %s", (surat_id,))
    conn.close()

    if not surat:
        return jsonify({'error': 'Surat not found'}), 404

    # Parse JSON fields
    if surat.get('barang_items'):
        try:
            surat['barang_items'] = json.loads(surat['barang_items'])
        except (json.JSONDecodeError, TypeError):
            pass

    return jsonify({'success': True, 'data': surat})


@api_external_bp.route('/surat/<int:surat_id>/status')
@require_api_key
def get_surat_status(surat_id):
    """Get approval status of a surat."""
    conn = get_db()
    surat = query_one(conn, """
        SELECT id, no_surat, status,
               approval_user, approval_user_at,
               approval_satpam, approval_satpam_at,
               approval_asman, approval_asman_at,
               approval_manager, approval_manager_at
        FROM surat_izin WHERE id = %s
    """, (surat_id,))
    conn.close()

    if not surat:
        return jsonify({'error': 'Surat not found'}), 404

    return jsonify({'success': True, 'data': surat})


# ---------------------------------------------------------------------------
# Statistics Endpoints
# ---------------------------------------------------------------------------

@api_external_bp.route('/stats/summary')
@require_api_key
def get_stats_summary():
    """Get summary statistics."""
    conn = get_db()

    stats = {}

    for status in ['pending', 'review', 'approved', 'rejected']:
        row = query_one(conn,
            "SELECT COUNT(*) as c FROM surat_izin WHERE status = %s", (status,))
        stats[f'total_{status}'] = row['c'] if row else 0

    row = query_one(conn, "SELECT COUNT(*) as c FROM surat_izin")
    stats['total'] = row['c'] if row else 0

    # Monthly
    monthly = query_all(conn, """
        SELECT DATE_FORMAT(tanggal, '%%Y-%%m') as month,
               COUNT(*) as count
        FROM surat_izin
        WHERE tanggal >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        GROUP BY DATE_FORMAT(tanggal, '%%Y-%%m')
        ORDER BY month
    """)

    conn.close()

    return jsonify({
        'success': True,
        'data': {
            'summary': stats,
            'monthly': monthly
        }
    })


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@api_external_bp.route('/health')
def health_check():
    """Health check endpoint (no auth required)."""
    try:
        conn = get_db()
        row = query_one(conn, "SELECT 1 as health")
        conn.close()
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

@api_external_bp.route('/version')
def get_version():
    """Get API version."""
    return jsonify({
        'version': '1.0.0',
        'name': 'Surat Izin API',
        'documentation': '/api/v1/docs'
    })
