"""
User management routes.
Handles user listing, role changes, and activation/deactivation.
"""
import bcrypt
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.database import get_db
from app.utils.decorators import role_required
from app.utils.helpers import query_all, query_one, execute, log_activity

users_bp = Blueprint('users', __name__)


def generate_username(nama_lengkap):
    """
    Generate a unique username from full name.
    Format: lowercase, remove special chars, add random suffix if needed.
    """
    # Clean the name - remove special chars, lowercase
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', nama_lengkap)
    clean = clean.strip().lower().replace(' ', '_')

    # If name is too short, add prefix
    if len(clean) < 3:
        clean = 'user_' + clean

    # Truncate if too long (leave room for suffix)
    base = clean[:20] if len(clean) > 20 else clean

    return base


def generate_unique_username(conn, base_username):
    """
    Generate a unique username by adding numeric suffix if needed.
    """
    # Check if base username exists
    existing = query_one(conn, "SELECT id FROM users WHERE username=%s", (base_username,))

    if not existing:
        return base_username

    # Add random suffix
    import random
    import string

    for _ in range(100):  # Try up to 100 times
        suffix = ''.join(random.choices(string.digits, k=3))
        new_username = f"{base_username}{suffix}"
        existing = query_one(conn, "SELECT id FROM users WHERE username=%s", (new_username,))
        if not existing:
            return new_username

    # Fallback: use timestamp-based username
    from datetime import datetime
    timestamp = datetime.now().strftime('%H%M%S')
    return f"{base_username}{timestamp}"


@users_bp.route('/users')
@login_required
@role_required('admin')
def user_list():
    """List all users (admin only)."""
    conn = get_db()
    users = query_all(conn, "SELECT * FROM users ORDER BY created_at DESC")
    conn.close()
    return render_template('users.html', users=users)


@users_bp.route('/users/create', methods=['POST'])
@login_required
@role_required('admin')
def create_user():
    """Create a new user (admin only)."""
    password = request.form.get('password', '')
    nama = request.form.get('nama_lengkap', '').strip()
    role = request.form.get('role', 'staff')
    divisi = request.form.get('divisi', '').strip()

    # Validation
    if not password or not nama:
        flash('Password dan nama lengkap wajib diisi.', 'danger')
        return redirect(url_for('users.user_list'))

    if len(password) < 6:
        flash('Password minimal 6 karakter.', 'danger')
        return redirect(url_for('users.user_list'))

    if len(nama) < 2:
        flash('Nama lengkap minimal 2 karakter.', 'danger')
        return redirect(url_for('users.user_list'))

    if role not in ('admin', 'user', 'staff', 'manager', 'satpam', 'asman'):
        flash('Role tidak valid.', 'danger')
        return redirect(url_for('users.user_list'))

    # Generate username automatically
    conn = get_db()
    base_username = generate_username(nama)
    username = generate_unique_username(conn, base_username)

    # Hash password
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    try:
        execute(conn,
                "INSERT INTO users (username, password, nama_lengkap, role, divisi) VALUES (%s, %s, %s, %s, %s)",
                (username, hashed, nama, role, divisi))
        flash(f'User "{nama}" berhasil ditambahkan. Username: {username}', 'success')
        log_activity(current_user.id, 'CREATE_USER', f'Created user: {username}')
    except Exception as e:
        flash('Terjadi kesalahan saat membuat user.', 'danger')
    finally:
        conn.close()

    return redirect(url_for('users.user_list'))


@users_bp.route('/users/<int:uid>/toggle')
@login_required
@role_required('admin')
def toggle_user(uid):
    """Toggle user active status (admin only)."""
    # Cannot deactivate self
    if uid == current_user.id:
        flash('Tidak bisa menonaktifkan diri sendiri.', 'danger')
        return redirect(url_for('users.user_list'))

    conn = get_db()
    u = query_one(conn, "SELECT is_active, role FROM users WHERE id=%s", (uid,))

    if not u:
        conn.close()
        flash('User tidak ditemukan.', 'danger')
        return redirect(url_for('users.user_list'))

    # Cannot deactivate admin users
    if u['role'] == 'admin':
        conn.close()
        flash('Tidak bisa menonaktifkan user dengan role Admin.', 'danger')
        return redirect(url_for('users.user_list'))

    execute(conn, "UPDATE users SET is_active=%s WHERE id=%s",
            (0 if u['is_active'] else 1, uid))
    status = 'dinonaktifkan' if u['is_active'] else 'diaktifkan'
    flash(f'User berhasil {status}.', 'success')
    log_activity(current_user.id, 'TOGGLE_USER', f'Toggled user #{uid} to {status}')
    conn.close()
    return redirect(url_for('users.user_list'))


@users_bp.route('/users/<int:uid>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(uid):
    """Delete a user (admin only)."""
    # Cannot delete self
    if uid == current_user.id:
        flash('Tidak bisa menghapus diri sendiri.', 'danger')
        return redirect(url_for('users.user_list'))

    conn = get_db()
    u = query_one(conn, "SELECT role, nama_lengkap FROM users WHERE id=%s", (uid,))

    if not u:
        conn.close()
        flash('User tidak ditemukan.', 'danger')
        return redirect(url_for('users.user_list'))

    # Cannot delete admin users
    if u['role'] == 'admin':
        conn.close()
        flash('Tidak bisa menghapus user dengan role Admin.', 'danger')
        return redirect(url_for('users.user_list'))

    # Delete the user
    execute(conn, "DELETE FROM users WHERE id=%s", (uid,))
    flash(f'User "{u["nama_lengkap"]}" berhasil dihapus.', 'success')
    log_activity(current_user.id, 'DELETE_USER', f'Deleted user #{uid}: {u["nama_lengkap"]}')
    conn.close()
    return redirect(url_for('users.user_list'))


@users_bp.route('/users/<int:uid>/edit', methods=['POST'])
@login_required
@role_required('admin')
def edit_user(uid):
    """Edit user details (admin only)."""
    conn = get_db()
    u = query_one(conn, "SELECT role, username FROM users WHERE id=%s", (uid,))

    if not u:
        conn.close()
        flash('User tidak ditemukan.', 'danger')
        return redirect(url_for('users.user_list'))

    # Cannot edit admin users
    if u['role'] == 'admin':
        conn.close()
        flash('Tidak bisa mengedit user Admin.', 'danger')
        return redirect(url_for('users.user_list'))

    nama = request.form.get('nama_lengkap', '').strip()
    divisi = request.form.get('divisi', '').strip()
    role = request.form.get('role', u['role'])
    new_password = request.form.get('password_baru', '').strip()

    if not nama or len(nama) < 2:
        conn.close()
        flash('Nama lengkap minimal 2 karakter.', 'danger')
        return redirect(url_for('users.user_list'))

    # Validate role
    if role not in ('user', 'staff', 'manager', 'satpam', 'asman'):
        flash('Role tidak valid.', 'danger')
        return redirect(url_for('users.user_list'))

    # Update user info (username cannot be changed)
    execute(conn, "UPDATE users SET nama_lengkap=%s, divisi=%s, role=%s WHERE id=%s",
            (nama, divisi, role, uid))

    # Update password if provided
    if new_password:
        if len(new_password) < 6:
            conn.close()
            flash('Password minimal 6 karakter.', 'danger')
            return redirect(url_for('users.user_list'))

        hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        execute(conn, "UPDATE users SET password=%s WHERE id=%s", (hashed, uid))
        flash(f'Data dan password user berhasil diperbarui. Username: {u["username"]}', 'success')
    else:
        flash(f'Data user berhasil diperbarui. Username: {u["username"]}', 'success')

    log_activity(current_user.id, 'EDIT_USER', f'Edited user #{uid}')
    conn.close()
    return redirect(url_for('users.user_list'))


@users_bp.route('/users/<int:uid>/role', methods=['POST'])
@login_required
@role_required('admin')
def change_role(uid):
    """Change user role (admin only)."""
    # Cannot change own role
    if uid == current_user.id:
        flash('Tidak bisa mengubah role diri sendiri.', 'danger')
        return redirect(url_for('users.user_list'))

    new_role = request.form.get('role')
    if new_role not in ('admin', 'user', 'staff', 'manager', 'satpam', 'asman'):
        flash('Role tidak valid.', 'danger')
        return redirect(url_for('users.user_list'))

    conn = get_db()
    u = query_one(conn, "SELECT role FROM users WHERE id=%s", (uid,))

    if not u:
        conn.close()
        flash('User tidak ditemukan.', 'danger')
        return redirect(url_for('users.user_list'))

    # Cannot change role of admin users
    if u['role'] == 'admin':
        conn.close()
        flash('Tidak bisa mengubah role user Admin.', 'danger')
        return redirect(url_for('users.user_list'))

    execute(conn, "UPDATE users SET role=%s WHERE id=%s", (new_role, uid))
    flash(f'Role user berhasil diubah menjadi {new_role}.', 'success')
    log_activity(current_user.id, 'CHANGE_ROLE', f'Changed user #{uid} role to {new_role}')
    conn.close()
    return redirect(url_for('users.user_list'))
