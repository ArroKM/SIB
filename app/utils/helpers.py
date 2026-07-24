"""
Helper functions for database operations and notifications.
"""
import json
from flask import request

from app.config import Config


# ---------------------------------------------------------------------------
# File Upload Helpers
# ---------------------------------------------------------------------------

ALLOWED_EXT = Config.ALLOWED_EXTENSIONS
ALLOWED_DOC_EXT = Config.ALLOWED_DOC_EXTENSIONS


def allowed_file(filename):
    """Check if filename has an allowed image extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def allowed_doc(filename):
    """Check if filename has an allowed document extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOC_EXT


# ---------------------------------------------------------------------------
# Database Query Helpers
# ---------------------------------------------------------------------------

def query_all(conn, sql, params=None):
    """Execute a query and return all results as list of dicts."""
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(conn, sql, params=None):
    """Execute a query and return a single dict or None."""
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(conn, sql, params=None):
    """Execute a write query, commit, and return lastrowid."""
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Lampiran Foto Parser
# ---------------------------------------------------------------------------

def parse_foto_list(lampiran_foto):
    """Parse lampiran_foto field into a list of filenames.

    Handles both legacy single-filename strings and the new JSON-array format.
    Always returns a (possibly empty) list.
    """
    if not lampiran_foto:
        return []
    try:
        parsed = json.loads(lampiran_foto)
        if isinstance(parsed, list):
            return [f for f in parsed if f]
        return [str(parsed)] if parsed else []
    except (json.JSONDecodeError, TypeError):
        return [lampiran_foto] if lampiran_foto else []


# ---------------------------------------------------------------------------
# Activity Logging
# ---------------------------------------------------------------------------

def log_activity(user_id, action, description):
    """Log a user activity."""
    from app.database import get_db

    try:
        conn = get_db()
        execute(conn,
                "INSERT INTO log_activity (user_id,action,description,ip_address) VALUES (%s,%s,%s,%s)",
                (user_id, action, description, request.remote_addr))
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def notify_user(user_id, title, message, link=None):
    """Create a notification for a specific user."""
    from app.database import get_db

    try:
        conn = get_db()
        execute(conn,
                "INSERT INTO notifications (user_id,title,message,link) VALUES (%s,%s,%s,%s)",
                (user_id, title, message, link))
        conn.close()
    except Exception:
        pass


def notify_admins(title, message, link=None, exclude_user=None):
    """Send notification to all admin, manager, satpam, and asman users."""
    from app.database import get_db

    try:
        conn = get_db()
        admins = query_all(conn,
            "SELECT id FROM users WHERE role IN ('admin','manager','satpam','asman') AND is_active=1")
        for a in admins:
            if exclude_user and a['id'] == exclude_user:
                continue
            execute(conn,
                    "INSERT INTO notifications (user_id,title,message,link) VALUES (%s,%s,%s,%s)",
                    (a['id'], title, message, link))
        conn.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Report Helpers
# ---------------------------------------------------------------------------

def build_barang_query(params):
    """Build SQL query and param list from filter request args for barang report."""
    jenis = params.get('jenis', '')
    status = params.get('status', '')
    date_from = params.get('date_from', '')
    date_to = params.get('date_to', '')
    search = params.get('q', '')

    q = "SELECT * FROM surat_izin WHERE 1=1"
    p = []
    if jenis:
        q += " AND jenis=%s"; p.append(jenis)
    if status:
        q += " AND status=%s"; p.append(status)
    if date_from:
        q += " AND tanggal >= %s"; p.append(date_from)
    if date_to:
        q += " AND tanggal <= %s"; p.append(date_to)
    if search:
        q += " AND (no_surat LIKE %s OR nama LIKE %s OR perusahaan LIKE %s)"
        p.extend([f'%{search}%'] * 3)
    q += " ORDER BY tanggal DESC"
    return q, p


def flatten_barang(rows):
    """Flatten surat rows into per-item barang records for reporting."""
    items = []
    for r in rows:
        try:
            barang = json.loads(r['barang_items']) if r['barang_items'] else []
        except (json.JSONDecodeError, TypeError):
            barang = []
        for b in barang:
            items.append({
                'surat_id': r['id'],
                'jenis': r['jenis'],
                'no_surat': r['no_surat'],
                'tanggal': r['tanggal'],
                'divisi': r['divisi'],
                'nama_pemohon': r['nama'],
                'perusahaan': r['perusahaan'],
                'status': r['status'],
                'nama_barang': b.get('nama_barang', ''),
                'jumlah': b.get('jumlah', ''),
                'satuan': b.get('satuan', ''),
                'keterangan': b.get('keterangan', ''),
                'foto': b.get('foto', []),
                'approval_user': b.get('approval_user', ''),
                'approval_satpam': b.get('approval_satpam', ''),
            })
    return items


# ---------------------------------------------------------------------------
# Professional Email Templates
# ---------------------------------------------------------------------------

def get_email_template(title, content, footer=True):
    """Generate professional HTML email template."""
    return f'''
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Arial,sans-serif;font-size:14px;color:#1a1a2e;background-color:#f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;padding:20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#0ea5e9 100%);padding:30px;text-align:center;">
                            <h1 style="color:#ffffff;margin:0;font-size:20px;font-weight:700;">PT PLN Indonesia Power</h1>
                            <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:12px;">UBP Jawa Tengah 2 Adipala</p>
                        </td>
                    </tr>
                    <!-- Content -->
                    <tr>
                        <td style="padding:30px;">
                            {content}
                        </td>
                    </tr>
                    <!-- Footer -->
                    {"<tr><td style=\"background-color:#f8fafc;padding:20px 30px;border-top:1px solid #e2e8f0;text-align:center;\"><p style=\"color:#64748b;font-size:12px;margin:0;\">Email ini dikirim secara otomatis oleh sistem.<br>Jangan balas email ini.<br><br><strong>PT PLN Indonesia Power UBP Jawa Tengah 2 Adipala</strong></p></td></tr>" if footer else ""}
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
'''


def get_approval_email_template(user_name, surat_no, jenis, action, urgency=''):
    """Generate approval notification email."""
    icon = '&#10004;' if 'approve' in action.lower() or 'setuju' in action.lower() else '&#10006;'
    icon_color = '#16a34a' if 'approve' in action.lower() or 'setuju' in action.lower() else '#dc2626'

    content = f'''
    <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-block;width:60px;height:60px;background-color:{icon_color};border-radius:50%;line-height:60px;font-size:30px;color:#ffffff;margin-bottom:16px;">{icon}</div>
        <h2 style="margin:0 0 8px;color:#1a1a2e;">Aksi Required</h2>
        <p style="margin:0;color:#64748b;">Ada surat yang memerlukan perhatian Anda</p>
    </div>

    <div style="background-color:#f8fafc;border-radius:8px;padding:20px;margin-bottom:20px;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
                    <strong style="color:#64748b;">No. Surat:</strong>
                </td>
                <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;text-align:right;">
                    <strong style="color:#1a1a2e;">{surat_no}</strong>
                </td>
            </tr>
            <tr>
                <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
                    <strong style="color:#64748b;">Jenis:</strong>
                </td>
                <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;text-align:right;">
                    <span style="background-color:{'#fee2e2' if jenis == 'keluar' else '#dcfce7'};color:{'#dc2626' if jenis == 'keluar' else '#16a34a'};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;">
                        {'SURAT KELUAR' if jenis == 'keluar' else 'SURAT MASUK'}
                    </span>
                </td>
            </tr>
            <tr>
                <td style="padding:8px 0;">
                    <strong style="color:#64748b;">Aksi:</strong>
                </td>
                <td style="padding:8px 0;text-align:right;">
                    <span style="color:#1a1a2e;">{action}</span>
                </td>
            </tr>
        </table>
    </div>

    <p style="margin-bottom:20px;">Yth. <strong>{user_name}</strong>,</p>
    <p style="margin-bottom:20px;line-height:1.6;">Terdapat surat izin yang memerlukan persetujuan Anda. Silakan login ke sistem untuk melihat detail dan mengambil tindakan.</p>
    '''

    return get_email_template('Notifikasi Persetujuan Surat', content)


def get_status_change_email_template(user_name, surat_no, old_status, new_status):
    """Generate status change notification email."""
    status_colors = {
        'approved': ('#16a34a', '#dcfce7', 'Disetujui'),
        'rejected': ('#dc2626', '#fee2e2', 'Ditolak'),
        'review': ('#d97706', '#fef3c7', 'Sedang Direview'),
        'pending': ('#64748b', '#f1f5f9', 'Pending'),
    }

    color, bg_color, label = status_colors.get(new_status, ('#64748b', '#f1f5f9', new_status))

    content = f'''
    <div style="text-align:center;margin-bottom:24px;">
        <div style="display:inline-block;width:60px;height:60px;background-color:{color};border-radius:50%;line-height:60px;font-size:30px;color:#ffffff;margin-bottom:16px;">&#10004;</div>
        <h2 style="margin:0 0 8px;color:#1a1a2e;">Status Diperbarui</h2>
        <p style="margin:0;color:#64748b;">Status surat Anda telah berubah</p>
    </div>

    <div style="background-color:#f8fafc;border-radius:8px;padding:20px;margin-bottom:20px;">
        <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
                <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;">
                    <strong style="color:#64748b;">No. Surat:</strong>
                </td>
                <td style="padding:8px 0;border-bottom:1px solid #e2e8f0;text-align:right;">
                    <strong style="color:#1a1a2e;">{surat_no}</strong>
                </td>
            </tr>
            <tr>
                <td style="padding:8px 0;">
                    <strong style="color:#64748b;">Status Baru:</strong>
                </td>
                <td style="padding:8px 0;text-align:right;">
                    <span style="background-color:{bg_color};color:{color};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600;">
                        {label}
                    </span>
                </td>
            </tr>
        </table>
    </div>

    <p style="margin-bottom:20px;">Yth. <strong>{user_name}</strong>,</p>
    <p style="margin-bottom:20px;line-height:1.6;">Status pengajuan surat izin Anda telah diubah menjadi <strong>{label}</strong>.</p>
    '''

    return get_email_template('Status Surat Diperbarui', content)
