"""
Notification routes.
Handles notification display and management.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from app.database import get_db
from app.utils.decorators import role_required
from app.utils.helpers import query_all, query_one, execute

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/notifications')
@login_required
def notifications_page():
    """Display user notifications page."""
    conn = get_db()
    notifs = query_all(conn,
        "SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50",
        (current_user.id,))
    conn.close()
    return render_template('notifications.html', notifications=notifs)


@notifications_bp.route('/activity')
@login_required
@role_required('admin')
def activity_log():
    """Display activity log (admin only)."""
    conn = get_db()
    logs = query_all(conn, """
        SELECT l.*, u.username FROM log_activity l
        LEFT JOIN users u ON l.user_id=u.id
        ORDER BY l.created_at DESC LIMIT 100
    """)
    conn.close()
    return render_template('activity.html', logs=logs)


@notifications_bp.route('/api/notifications')
@login_required
def api_list():
    """API endpoint for notifications (GET request - no CSRF needed)."""
    conn = get_db()
    notifs = query_all(conn,
        "SELECT * FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 20",
        (current_user.id,))
    conn.close()

    result = []
    for n in notifs:
        result.append({
            'id': n['id'],
            'title': n['title'],
            'message': n['message'],
            'link': n['link'],
            'is_read': n['is_read'],
            'created_at': str(n['created_at']) if n['created_at'] else None,
        })
    return jsonify(result)


@notifications_bp.route('/api/notifications/read', methods=['POST'])
@login_required
def api_mark_all_read():
    """
    Mark all notifications as read (API endpoint).
    CSRF protection is handled by including X-CSRFToken header in JavaScript.
    """
    conn = get_db()
    execute(conn, "UPDATE notifications SET is_read=1 WHERE user_id=%s AND is_read=0",
            (current_user.id,))
    conn.close()
    return jsonify(success=True)


@notifications_bp.route('/api/notifications/<int:nid>/read', methods=['POST'])
@login_required
def api_mark_read(nid):
    """
    Mark a single notification as read (API endpoint).
    CSRF protection is handled by including X-CSRFToken header in JavaScript.
    """
    conn = get_db()
    execute(conn, "UPDATE notifications SET is_read=1 WHERE id=%s AND user_id=%s",
            (nid, current_user.id))
    conn.close()
    return jsonify(success=True)
