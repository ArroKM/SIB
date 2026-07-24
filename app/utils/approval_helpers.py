"""
Approval Helpers Module.
Handles flexible approval chains, delegation, escalation, and anti-fraud checks.
"""
import hashlib
import json
from datetime import datetime, date, timedelta
from functools import wraps

from app.database import get_db
from app.utils.helpers import query_one, query_all, execute


# ============================================================================
# APPROVAL CHAINS
# ============================================================================

def get_approval_chain(surat_id=None, urgency='normal'):
    """
    Get the appropriate approval chain based on settings and urgency.

    Returns list of stages: ['user', 'satpam', 'asman', 'manager']
    """
    if surat_id:
        # Check if surat has custom approval chain
        conn = get_db()
        surat = query_one(conn, "SELECT approval_chain, urgency FROM surat_izin WHERE id=%s", (surat_id,))
        conn.close()

        if surat and surat.get('approval_chain'):
            try:
                chain = json.loads(surat['approval_chain'])
                if chain:
                    return chain
            except (json.JSONDecodeError, TypeError):
                pass

            # Also use urgency from surat if set
            if surat.get('urgency'):
                urgency = surat['urgency']

    # Get chain based on urgency
    conn = get_db()
    setting_key = f'approval_chain_{urgency}'
    setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key=%s", (setting_key,))
    conn.close()

    if setting and setting.get('setting_value'):
        try:
            chain = json.loads(setting['setting_value'])
            return chain if chain else ['user', 'satpam', 'manager']
        except (json.JSONDecodeError, TypeError):
            pass

    # Default chain
    default_chains = {
        'normal': ['user', 'satpam', 'manager'],
        'urgent': ['manager'],
    }
    return default_chains.get(urgency, ['user', 'satpam', 'manager'])


def is_stage_in_chain(surat_id, stage):
    """Check if a stage is in the surat's approval chain."""
    chain = get_approval_chain(surat_id)
    return stage in chain


def get_current_stage(surat):
    """
    Get the current approval stage for a surat.
    Returns the stage that needs to be approved next.
    """
    chain = get_approval_chain(surat.get('id'), surat.get('urgency', 'normal'))

    stage_status_map = {
        'user': surat.get('approval_user', 'pending'),
        'satpam': surat.get('approval_satpam', 'pending'),
        'asman': surat.get('approval_asman', 'pending'),
        'manager': surat.get('approval_manager', 'pending'),
    }

    for stage in chain:
        status = stage_status_map.get(stage, 'pending')
        if status == 'pending':
            return stage

    # All stages completed
    return None


def get_approval_progress(surat):
    """
    Get approval progress percentage.
    Returns (completed, total, percentage)
    """
    chain = get_approval_chain(surat.get('id'), surat.get('urgency', 'normal'))
    total = len(chain)

    if total == 0:
        return 0, 0, 0

    completed = 0
    stage_status_map = {
        'user': surat.get('approval_user', 'pending'),
        'satpam': surat.get('approval_satpam', 'pending'),
        'asman': surat.get('approval_asman', 'pending'),
        'manager': surat.get('approval_manager', 'pending'),
    }

    for stage in chain:
        status = stage_status_map.get(stage, 'pending')
        if status in ('sesuai', 'approved'):
            completed += 1

    percentage = int((completed / total) * 100) if total > 0 else 0
    return completed, total, percentage


def set_surat_approval_chain(surat_id, chain, urgency='normal'):
    """Set custom approval chain for a surat."""
    conn = get_db()
    try:
        execute(conn,
            "UPDATE surat_izin SET approval_chain=%s, urgency=%s WHERE id=%s",
            (json.dumps(chain), urgency, surat_id)
        )
    finally:
        conn.close()


# ============================================================================
# DELEGATION SYSTEM
# ============================================================================

def check_delegation(delegator_id, stage, check_date=None):
    """
    Check if a user has active delegation from another user for a stage.
    Returns (has_delegation, actual_delegator_id) or (False, None)
    """
    if check_date is None:
        check_date = date.today()

    conn = get_db()

    # Find active delegation where this user is the delegate
    delegation = query_one(conn, """
        SELECT d.*, u.nama_lengkap as delegator_name
        FROM approval_delegations d
        JOIN users u ON d.delegator_id = u.id
        WHERE d.delegate_id = %s
          AND d.is_active = 1
          AND d.start_date <= %s
          AND d.end_date >= %s
    """, (delegator_id, check_date, check_date))

    conn.close()

    if delegation and delegation.get('stages'):
        try:
            stages = json.loads(delegation['stages'])
            if stage in stages:
                return True, delegation['delegator_id'], delegation['delegator_name']
        except (json.JSONDecodeError, TypeError):
            pass

    return False, None, None


def get_active_delegations(user_id):
    """Get all active delegations for a user (as delegator or delegate)."""
    conn = get_db()
    today = date.today()

    # Delegations where user is the delegator
    outgoing = query_all(conn, """
        SELECT d.*, u.nama_lengkap as delegate_name
        FROM approval_delegations d
        JOIN users u ON d.delegate_id = u.id
        WHERE d.delegator_id = %s
          AND d.is_active = 1
          AND d.start_date <= %s
          AND d.end_date >= %s
    """, (user_id, today, today))

    # Delegations where user is the delegate
    incoming = query_all(conn, """
        SELECT d.*, u.nama_lengkap as delegator_name
        FROM approval_delegations d
        JOIN users u ON d.delegator_id = u.id
        WHERE d.delegate_id = %s
          AND d.is_active = 1
          AND d.start_date <= %s
          AND d.end_date >= %s
    """, (user_id, today, today))

    conn.close()

    return {
        'outgoing': outgoing,  # Delegations I've given to others
        'incoming': incoming  # Delegations others have given to me
    }


def create_delegation(delegator_id, delegate_id, stages, start_date, end_date, reason=None):
    """Create a new delegation."""
    conn = get_db()
    sid = execute(conn, """
        INSERT INTO approval_delegations
        (delegator_id, delegate_id, stages, start_date, end_date, reason, created_by)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (delegator_id, delegate_id, json.dumps(stages), start_date, end_date, reason, delegator_id))
    conn.close()
    return sid


def revoke_delegation(delegation_id, user_id):
    """Revoke a delegation."""
    conn = get_db()
    execute(conn,
        "UPDATE approval_delegations SET is_active = 0 WHERE id = %s AND delegator_id = %s",
        (delegation_id, user_id)
    )
    conn.close()


# ============================================================================
# REMINDER & ESCALATION
# ============================================================================

def check_pending_approvals_for_reminder(user_id):
    """
    Check if user has pending approvals and get time info.
    Returns list of surat with pending time.
    """
    conn = get_db()
    today = date.today()

    # Get user's role
    user = query_one(conn, "SELECT role FROM users WHERE id=%s", (user_id,))
    if not user:
        conn.close()
        return []

    role = user['role']

    # Build query based on role
    pending_surat = []

    if role in ('user', 'pemberi_kerja'):
        rows = query_all(conn, """
            SELECT s.id, s.no_surat, s.jenis, s.nama, s.created_at,
                   TIMESTAMPDIFF(HOUR, COALESCE(s.approval_user_at, s.created_at), NOW()) as pending_hours
            FROM surat_izin s
            WHERE s.approval_user = 'pending'
              AND (s.created_by != %s OR s.created_by IS NULL)
            ORDER BY pending_hours DESC
        """, (user_id,))
        pending_surat = rows

    elif role == 'satpam':
        rows = query_all(conn, """
            SELECT s.id, s.no_surat, s.jenis, s.nama, s.created_at,
                   TIMESTAMPDIFF(HOUR, COALESCE(s.approval_satpam_at, s.approval_user_at, s.created_at), NOW()) as pending_hours
            FROM surat_izin s
            WHERE s.approval_user IN ('sesuai', 'tidak_sesuai')
              AND s.approval_satpam = 'pending'
            ORDER BY pending_hours DESC
        """, ())
        pending_surat = rows

    elif role == 'asman':
        rows = query_all(conn, """
            SELECT s.id, s.no_surat, s.jenis, s.nama, s.created_at,
                   TIMESTAMPDIFF(HOUR, COALESCE(s.approval_asman_at, s.approval_satpam_at, s.created_at), NOW()) as pending_hours
            FROM surat_izin s
            WHERE s.approval_satpam IN ('sesuai', 'tidak_sesuai')
              AND s.approval_asman = 'pending'
            ORDER BY pending_hours DESC
        """, ())
        pending_surat = rows

    elif role == 'manager':
        rows = query_all(conn, """
            SELECT s.id, s.no_surat, s.jenis, s.nama, s.created_at,
                   TIMESTAMPDIFF(HOUR, COALESCE(s.approval_manager_at, s.approval_asman_at, s.created_at), NOW()) as pending_hours
            FROM surat_izin s
            WHERE s.approval_asman IN ('approved', 'rejected')
              AND s.approval_manager = 'pending'
            ORDER BY pending_hours DESC
        """, ())
        pending_surat = rows

    conn.close()
    return pending_surat


def get_pending_count_by_role():
    """Get count of pending approvals by role."""
    conn = get_db()

    stats = {
        'user': 0,
        'satpam': 0,
        'asman': 0,
        'manager': 0,
    }

    # User/Pemberi Kerja pending
    row = query_one(conn, "SELECT COUNT(*) as c FROM surat_izin WHERE approval_user = 'pending'")
    stats['user'] = row['c'] if row else 0

    # Satpam pending
    row = query_one(conn, """
        SELECT COUNT(*) as c FROM surat_izin
        WHERE approval_user IN ('sesuai', 'tidak_sesuai') AND approval_satpam = 'pending'
    """)
    stats['satpam'] = row['c'] if row else 0

    # Asman pending
    row = query_one(conn, """
        SELECT COUNT(*) as c FROM surat_izin
        WHERE approval_satpam IN ('sesuai', 'tidak_sesuai') AND approval_asman = 'pending'
    """)
    stats['asman'] = row['c'] if row else 0

    # Manager pending
    row = query_one(conn, """
        SELECT COUNT(*) as c FROM surat_izin
        WHERE approval_asman IN ('approved', 'rejected') AND approval_manager = 'pending'
    """)
    stats['manager'] = row['c'] if row else 0

    conn.close()
    return stats


def should_send_reminder(user_id, stage):
    """Check if reminder should be sent based on settings."""
    conn = get_db()

    # Get reminder hours setting
    setting_key = f'reminder_hours_{stage}'
    setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key=%s", (setting_key,))
    conn.close()

    if not setting or not setting.get('setting_value'):
        # Default reminder hours
        default_hours = {'user': 4, 'satpam': 8, 'asman': 12, 'manager': 24}
        reminder_hours = default_hours.get(stage, 24)
    else:
        reminder_hours = int(setting['setting_value'])

    # Check if user has pending approvals exceeding reminder hours
    pending = check_pending_approvals_for_reminder(user_id)
    for p in pending:
        if p.get('pending_hours', 0) >= reminder_hours:
            return True, p

    return False, None


def escalate_surat(surat_id, escalation_level=1):
    """Mark a surat as escalated."""
    conn = get_db()
    try:
        execute(conn,
            "UPDATE surat_izin SET is_escalated = 1, escalation_level = %s WHERE id = %s",
            (escalation_level, surat_id)
        )
    finally:
        conn.close()


def check_and_escalate_overdue():
    """Check for overdue approvals and escalate."""
    conn = get_db()

    # Get escalation hours setting
    setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key='escalation_hours'")
    escalation_hours = int(setting['setting_value']) if setting and setting.get('setting_value') else 48

    # Find overdue surat
    overdue = query_all(conn, f"""
        SELECT id, no_surat FROM surat_izin
        WHERE status IN ('pending', 'review')
          AND is_escalated = 0
          AND (approval_user = 'pending' OR approval_satpam = 'pending' OR
               approval_asman = 'pending' OR approval_manager = 'pending')
          AND TIMESTAMPDIFF(HOUR, created_at, NOW()) > %s
    """, (escalation_hours,))

    conn.close()

    for s in overdue:
        escalate_surat(s['id'])
        # Notify admins
        from app.utils.helpers import notify_admins
        notify_admins(
            'Surat Overdue',
            f'Surat {s["no_surat"]} telah overdue dan di-eskalasi',
            f'/surat/{s["id"]}'
        )


# ============================================================================
# ANTI-FRAUD MEASURES
# ============================================================================

def check_blacklist(item_name):
    """Check if item name is in blacklist."""
    conn = get_db()

    # Check if blacklist is enabled
    setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key='blacklist_enabled'")
    if not setting or setting.get('setting_value') != '1':
        conn.close()
        return False, None

    # Check exact match
    item = query_one(conn, """
        SELECT * FROM blacklist_items
        WHERE item_name = %s AND is_active = 1
    """, (item_name,))

    if item:
        conn.close()
        return True, item.get('reason', 'Item terlarang')

    # Check pattern match
    items = query_all(conn, "SELECT * FROM blacklist_items WHERE is_active = 1")
    import re
    for item in items:
        if item.get('item_pattern'):
            try:
                if re.search(item['item_pattern'], item_name, re.IGNORECASE):
                    conn.close()
                    return True, item.get('reason', 'Item terlarang')
            except re.error:
                pass

    conn.close()
    return False, None


def check_high_value_double_approval(barang_items):
    """
    Check if total value exceeds threshold requiring double approval.
    Returns (requires_double, threshold, total_value)
    """
    conn = get_db()

    # Get threshold
    setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key='double_approval_threshold'")
    threshold = int(setting['setting_value']) if setting and setting.get('setting_value') else 50000000

    conn.close()

    # Calculate total (assuming jumlah represents value if not explicitly provided)
    # This is a simplified check - in real scenario you'd have harga field
    total_value = 0
    for item in barang_items:
        jumlah = item.get('jumlah', 1)
        harga = item.get('harga', 0)  # If harga field exists
        if harga:
            total_value += float(jumlah) * float(harga)

    return total_value >= threshold, threshold, total_value


def check_forbidden_hours():
    """
    Check if current time is in forbidden hours.
    Returns (is_forbidden, start_time, end_time)
    """
    conn = get_db()

    # Check if forbidden hours is enabled
    setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key='forbidden_hours_enabled'")
    if not setting or setting.get('setting_value') != '1':
        conn.close()
        return False, None, None

    # Get forbidden hours
    start_setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key='forbidden_hours_start'")
    end_setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key='forbidden_hours_end'")

    conn.close()

    start_time = start_setting['setting_value'] if start_setting else '22:00'
    end_time = end_setting['setting_value'] if end_setting else '06:00'

    now = datetime.now().time()
    from datetime import time
    start = time(int(start_time.split(':')[0]), int(start_time.split(':')[1]))
    end = time(int(end_time.split(':')[0]), int(end_time.split(':')[1]))

    # Handle overnight forbidden hours (e.g., 22:00 to 06:00)
    if start > end:
        is_forbidden = now >= start or now <= end
    else:
        is_forbidden = start <= now <= end

    return is_forbidden, start_time, end_time


# ============================================================================
# QR CODE & VERIFICATION
# ============================================================================

def generate_unique_hash(surat_id, no_surat):
    """Generate unique hash for QR code verification."""
    hash_input = f"{surat_id}-{no_surat}-{datetime.now().isoformat()}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


def set_surat_hash(surat_id, no_surat):
    """Generate and save unique hash for a surat."""
    hash_value = generate_unique_hash(surat_id, no_surat)
    conn = get_db()
    try:
        execute(conn, "UPDATE surat_izin SET unique_hash = %s WHERE id = %s", (hash_value, surat_id))
    finally:
        conn.close()
    return hash_value


def verify_surat_hash(surat_id, hash_value):
    """Verify if the hash matches the surat."""
    conn = get_db()
    surat = query_one(conn, "SELECT id, no_surat, status FROM surat_izin WHERE id = %s AND unique_hash = %s", (surat_id, hash_value))
    conn.close()
    return surat is not None


# ============================================================================
# SETTINGS HELPERS
# ============================================================================

def get_setting(key, default=None):
    """Get a setting value."""
    conn = get_db()
    setting = query_one(conn, "SELECT setting_value FROM surat_settings WHERE setting_key = %s", (key,))
    conn.close()
    return setting['setting_value'] if setting else default


def set_setting(key, value, updated_by=None):
    """Set a setting value."""
    conn = get_db()
    execute(conn,
        "INSERT INTO surat_settings (setting_key, setting_value, updated_by) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value), updated_by = VALUES(updated_by)",
        (key, str(value), updated_by)
    )
    conn.close()


# ============================================================================
# AUDIT LOG HELPERS
# ============================================================================

def log_audit(surat_id, user_id, action, stage=None, description=None,
              old_value=None, new_value=None, ip_address=None, user_agent=None, note=None):
    """Log an audit entry."""
    conn = get_db()
    execute(conn, """
        INSERT INTO audit_logs
        (surat_id, user_id, action, stage, description, old_value, new_value, ip_address, user_agent, note)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        surat_id,
        user_id,
        action,
        stage,
        description,
        json.dumps(old_value) if old_value else None,
        json.dumps(new_value) if new_value else None,
        ip_address,
        user_agent,
        note
    ))
    conn.close()


def get_audit_trail(surat_id):
    """Get audit trail for a surat."""
    conn = get_db()
    logs = query_all(conn, """
        SELECT a.*, u.nama_lengkap as user_name
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.surat_id = %s
        ORDER BY a.created_at DESC
    """, (surat_id,))
    conn.close()

    # Parse JSON fields
    for log in logs:
        if log.get('old_value'):
            try:
                log['old_value'] = json.loads(log['old_value'])
            except (json.JSONDecodeError, TypeError):
                pass
        if log.get('new_value'):
            try:
                log['new_value'] = json.loads(log['new_value'])
            except (json.JSONDecodeError, TypeError):
                pass

    return logs
