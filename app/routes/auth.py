"""
Authentication routes.
Handles login, register, and logout.
"""
import bcrypt
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user, login_required
from urllib.parse import urlparse

from app.database import get_db
from app.utils.helpers import query_one, execute, log_activity

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        conn = get_db()
        row = query_one(conn,
                        "SELECT * FROM users WHERE username=%s AND is_active=1",
                        (username,))
        conn.close()

        if row and bcrypt.checkpw(password.encode(), row['password'].encode()):
            from app.models.user import User
            login_user(User(row))
            log_activity(row['id'], 'LOGIN', f'{username} logged in')
            flash('Login berhasil!', 'success')

            nxt = request.args.get('next')
            if nxt and urlparse(nxt).netloc != '':
                nxt = None
            return redirect(nxt or url_for('dashboard.dashboard'))

        flash('Username atau password salah.', 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handle new user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        nama = request.form.get('nama_lengkap', '').strip()
        divisi = request.form.get('divisi', '').strip()

        if not all([username, password, nama]):
            flash('Semua field wajib diisi.', 'danger')
            return redirect(url_for('auth.register'))

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        conn = get_db()
        try:
            execute(conn,
                    "INSERT INTO users (username,password,nama_lengkap,role,divisi) VALUES (%s,%s,%s,%s,%s)",
                    (username, hashed, nama, 'staff', divisi))
            flash('Registrasi berhasil! Silakan login.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            flash('Username sudah digunakan.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    log_activity(current_user.id, 'LOGOUT', f'{current_user.username} logged out')
    logout_user()
    flash('Anda telah logout.', 'info')
    return redirect(url_for('auth.login'))
