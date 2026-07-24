"""
Surat (Letter/Permit) routes.
Handles all CRUD operations for surat izin.
"""
import io
import json
import os
import uuid
import base64
from datetime import date, datetime

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    flash, send_file, abort, current_app, jsonify,
)
from flask_login import login_required, current_user

from app.config import Config
from app.database import get_db
from app.utils.decorators import role_required
from app.utils.helpers import (
    query_all, query_one, execute,
    log_activity, notify_user, notify_admins,
    parse_foto_list, allowed_file, allowed_doc,
)

surat_bp = Blueprint('surat', __name__)


def generate_qr_code(data: str, size: int = 200) -> str:
    """
    Generate QR code as base64 data URL.
    Args:
        data: The data to encode in QR code
        size: Size of QR code in pixels
    Returns:
        Base64 data URL of the QR code image
    """
    import qrcode
    from qrcode.image.pure import PyPNGImage

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Resize if needed
    if size != 200:
        from PIL import Image
        img = img.resize((size, size), Image.LANCZOS)

    # Convert to bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    # Convert to base64
    img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
    return f"data:image/png;base64,{img_base64}"


# ---------------------------------------------------------------------------
# Surat List
# ---------------------------------------------------------------------------

@surat_bp.route('/surat')
@login_required
def surat_list():
    """List all surat izin with filtering."""
    jenis = request.args.get('jenis', '')
    status = request.args.get('status', '')
    search = request.args.get('q', '')

    q = "SELECT * FROM surat_izin WHERE 1=1"
    params = []
    if jenis:
        q += " AND jenis=%s"
        params.append(jenis)
    if status:
        q += " AND status=%s"
        params.append(status)
    if search:
        q += " AND (no_surat LIKE %s OR nama LIKE %s OR perusahaan LIKE %s)"
        params.extend([f'%{search}%'] * 3)
    q += " ORDER BY created_at DESC"

    conn = get_db()
    rows = query_all(conn, q, params)
    conn.close()

    return render_template('surat_list.html', surat_list=rows,
                          jenis=jenis, status=status, search=search)


# ---------------------------------------------------------------------------
# Add Surat
# ---------------------------------------------------------------------------

@surat_bp.route('/surat/add', methods=['GET', 'POST'])
@login_required
def add_surat():
    """Create a new surat izin with anti-fraud validation."""
    from app.utils.approval_helpers import check_blacklist, check_forbidden_hours, set_surat_hash
    import hashlib

    if request.method == 'POST':
        jenis = request.form.get('jenis', 'keluar')
        required = ['no_surat', 'tanggal', 'tgl_terbit', 'divisi', 'nama',
                     'badge', 'no_kendaraan', 'perusahaan', 'no_spk',
                     'pemohon', 'diperiksa_oleh', 'disetujui_oleh']
        for f in required:
            if not request.form.get(f):
                flash(f'Field {f} harus diisi!', 'danger')
                return redirect(url_for('add_surat'))

        # Check forbidden hours
        is_forbidden, start_time, end_time = check_forbidden_hours()
        if is_forbidden:
            flash(f'Tidak dapat membuat surat pada jam {start_time} - {end_time}. Hubungi admin.', 'danger')
            return redirect(url_for('add_surat'))

        # Handle KTP photo upload
        foto_ktp_name = None
        ktp_file = request.files.get('foto_ktp')
        if ktp_file and ktp_file.filename and allowed_file(ktp_file.filename):
            ext = ktp_file.filename.rsplit('.', 1)[1].lower()
            foto_ktp_name = f"{uuid.uuid4().hex}.{ext}"
            ktp_file.save(os.path.join(Config.UPLOAD_DIR, foto_ktp_name))

        # Handle SPK file upload
        file_spk_name = None
        spk_file = request.files.get('file_spk')
        if spk_file and spk_file.filename and allowed_doc(spk_file.filename):
            ext = spk_file.filename.rsplit('.', 1)[1].lower()
            file_spk_name = f"{uuid.uuid4().hex}.{ext}"
            spk_file.save(os.path.join(Config.UPLOAD_DIR, file_spk_name))

        try:
            barang = json.loads(request.form.get('barang_items', '[]'))
        except json.JSONDecodeError:
            flash('Format data barang tidak valid!', 'danger')
            return redirect(url_for('add_surat'))

        # Anti-fraud: Check blacklist for each item
        for item in barang:
            nama_barang = item.get('nama_barang', '')
            if nama_barang:
                is_blacklisted, reason = check_blacklist(nama_barang)
                if is_blacklisted:
                    flash(f'Barang "{nama_barang}" dalam blacklist: {reason}', 'danger')
                    return redirect(url_for('add_surat'))

        # Handle per-item photo uploads
        for i, item in enumerate(barang):
            item_fotos = request.files.getlist(f'foto_barang_{i}')
            item_foto_names = []
            for foto in item_fotos:
                if foto and foto.filename and allowed_file(foto.filename):
                    ext = foto.filename.rsplit('.', 1)[1].lower()
                    fname = f"{uuid.uuid4().hex}.{ext}"
                    foto.save(os.path.join(Config.UPLOAD_DIR, fname))
                    item_foto_names.append(fname)
            if item_foto_names:
                item['foto'] = item_foto_names

        # Get urgency from form (default: normal)
        urgency = request.form.get('urgency', 'normal')
        no_surat = request.form['no_surat'].strip()

        # Generate unique hash for QR code
        hash_input = f"{no_surat}-{datetime.now().isoformat()}"
        unique_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:32]

        conn = get_db()
        sid = execute(conn, """
            INSERT INTO surat_izin
            (jenis,no_surat,tanggal,tgl_terbit,divisi,nama,badge,no_kendaraan,
             perusahaan,no_spk,foto_ktp,file_spk,pemohon,diperiksa_oleh,disetujui_oleh,
             barang_items,lampiran_foto,status,urgency,unique_hash,created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            jenis,
            no_surat,
            request.form['tanggal'],
            request.form['tgl_terbit'],
            request.form['divisi'],
            request.form['nama'].strip(),
            request.form['badge'].strip(),
            request.form['no_kendaraan'].strip(),
            request.form['perusahaan'].strip(),
            request.form['no_spk'].strip(),
            foto_ktp_name,
            file_spk_name,
            request.form['pemohon'].strip(),
            request.form['diperiksa_oleh'].strip(),
            request.form['disetujui_oleh'].strip(),
            json.dumps(barang, ensure_ascii=False),
            None,  # lampiran_foto
            'pending',
            urgency,
            unique_hash,
            current_user.id,
        ))
        conn.close()

        log_activity(current_user.id, 'CREATE',
                     f'Surat {jenis} {no_surat} dibuat')
        notify_admins(
            'Surat Baru Dibuat',
            f'{current_user.nama_lengkap} membuat surat {jenis} {request.form["no_surat"]}',
            f'/surat/{sid}',
            exclude_user=current_user.id,
        )

        flash('Surat berhasil dibuat!', 'success')
        return redirect(url_for('surat.view_surat', id=sid))

    today = date.today().isoformat()
    jenis = request.args.get('jenis', 'keluar')
    return render_template('add_surat.html', date_now=today, jenis=jenis)


# ---------------------------------------------------------------------------
# View Surat
# ---------------------------------------------------------------------------

@surat_bp.route('/surat/<int:id>')
@login_required
def view_surat(id):
    """View a single surat izin."""
    conn = get_db()
    surat = query_one(conn, "SELECT * FROM surat_izin WHERE id=%s", (id,))
    if not surat:
        conn.close()
        flash('Surat tidak ditemukan.', 'danger')
        return redirect(url_for('surat.surat_list'))

    surat = dict(surat)
    try:
        surat['barang_items'] = json.loads(surat['barang_items'])
    except Exception:
        surat['barang_items'] = []
    surat['foto_list'] = parse_foto_list(surat.get('lampiran_foto'))

    # Look up approver names for signature section
    for key in ('approval_user_by', 'approval_satpam_by', 'approval_asman_by', 'approval_manager_by'):
        uid = surat.get(key)
        if uid:
            u = query_one(conn, "SELECT nama_lengkap FROM users WHERE id=%s", (uid,))
            surat[key + '_name'] = u['nama_lengkap'] if u else '-'
        else:
            surat[key + '_name'] = ''

    # Look up creator name
    creator_id = surat.get('created_by')
    if creator_id:
        creator = query_one(conn, "SELECT nama_lengkap FROM users WHERE id=%s", (creator_id,))
        surat['creator_name'] = creator['nama_lengkap'] if creator else '-'
    else:
        surat['creator_name'] = ''

    conn.close()
    return render_template('view_surat.html', surat=surat)


# ---------------------------------------------------------------------------
# Edit Surat
# ---------------------------------------------------------------------------

@surat_bp.route('/surat/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_surat(id):
    """Edit an existing surat izin."""
    conn = get_db()
    surat = query_one(conn, "SELECT * FROM surat_izin WHERE id=%s", (id,))
    if not surat:
        conn.close()
        flash('Surat tidak ditemukan.', 'danger')
        return redirect(url_for('surat.surat_list'))

    if request.method == 'POST':
        # Handle KTP photo upload
        foto_ktp_name = surat.get('foto_ktp')
        ktp_file = request.files.get('foto_ktp')
        if ktp_file and ktp_file.filename and allowed_file(ktp_file.filename):
            ext = ktp_file.filename.rsplit('.', 1)[1].lower()
            foto_ktp_name = f"{uuid.uuid4().hex}.{ext}"
            ktp_file.save(os.path.join(Config.UPLOAD_DIR, foto_ktp_name))

        # Handle SPK file upload
        file_spk_name = surat.get('file_spk')
        spk_file = request.files.get('file_spk')
        if spk_file and spk_file.filename and allowed_doc(spk_file.filename):
            ext = spk_file.filename.rsplit('.', 1)[1].lower()
            file_spk_name = f"{uuid.uuid4().hex}.{ext}"
            spk_file.save(os.path.join(Config.UPLOAD_DIR, file_spk_name))

        try:
            barang = json.loads(request.form.get('barang_items', '[]'))
        except json.JSONDecodeError:
            flash('Format data barang tidak valid!', 'danger')
            return redirect(url_for('edit_surat', id=id))

        # Handle per-item photo uploads
        for i, item in enumerate(barang):
            item_fotos = request.files.getlist(f'foto_barang_{i}')
            item_foto_names = item.get('foto', [])
            if not isinstance(item_foto_names, list):
                item_foto_names = []
            for foto in item_fotos:
                if foto and foto.filename and allowed_file(foto.filename):
                    ext = foto.filename.rsplit('.', 1)[1].lower()
                    fname = f"{uuid.uuid4().hex}.{ext}"
                    foto.save(os.path.join(Config.UPLOAD_DIR, fname))
                    item_foto_names.append(fname)
            if item_foto_names:
                item['foto'] = item_foto_names

        execute(conn, """
            UPDATE surat_izin SET
              jenis=%s,no_surat=%s,tanggal=%s,tgl_terbit=%s,divisi=%s,nama=%s,badge=%s,
              no_kendaraan=%s,perusahaan=%s,no_spk=%s,foto_ktp=%s,file_spk=%s,pemohon=%s,
              diperiksa_oleh=%s,disetujui_oleh=%s,barang_items=%s
            WHERE id=%s
        """, (
            request.form.get('jenis', surat['jenis']),
            request.form['no_surat'].strip(),
            request.form['tanggal'],
            request.form['tgl_terbit'],
            request.form['divisi'],
            request.form['nama'].strip(),
            request.form['badge'].strip(),
            request.form['no_kendaraan'].strip(),
            request.form['perusahaan'].strip(),
            request.form['no_spk'].strip(),
            foto_ktp_name,
            file_spk_name,
            request.form['pemohon'].strip(),
            request.form['diperiksa_oleh'].strip(),
            request.form['disetujui_oleh'].strip(),
            json.dumps(barang, ensure_ascii=False),
            id,
        ))
        conn.close()

        log_activity(current_user.id, 'UPDATE', f'Surat #{id} diperbarui')
        flash('Surat berhasil diperbarui!', 'success')
        return redirect(url_for('surat.view_surat', id=id))

    conn.close()
    surat = dict(surat)
    try:
        surat['barang_items'] = json.loads(surat['barang_items'])
    except Exception:
        surat['barang_items'] = []
    surat['foto_list'] = parse_foto_list(surat.get('lampiran_foto'))
    return render_template('edit_surat.html', surat=surat)


# ---------------------------------------------------------------------------
# Update Status
# ---------------------------------------------------------------------------

@surat_bp.route('/surat/<int:id>/status', methods=['POST'])
@login_required
@role_required('admin')
def update_status(id):
    """Update surat status (admin only)."""
    new_status = request.form.get('status')
    catatan = request.form.get('catatan', '')

    if new_status not in ('approved', 'rejected', 'pending', 'review'):
        flash('Status tidak valid.', 'danger')
        return redirect(url_for('surat.view_surat', id=id))

    conn = get_db()
    surat = query_one(conn, "SELECT no_surat, created_by FROM surat_izin WHERE id=%s", (id,))
    execute(conn, "UPDATE surat_izin SET status=%s, catatan=%s WHERE id=%s",
            (new_status, catatan, id))
    conn.close()

    log_activity(current_user.id, 'STATUS', f'Surat #{id} status → {new_status}')

    # Notify the surat creator about status change
    if surat and surat.get('created_by'):
        status_labels = {'approved': 'Disetujui', 'rejected': 'Ditolak',
                         'review': 'Sedang Direview', 'pending': 'Pending'}
        label = status_labels.get(new_status, new_status)
        notify_user(surat['created_by'],
                    f'Status Surat Diperbarui',
                    f'Surat {surat["no_surat"]} status diubah menjadi {label}',
                    f'/surat/{id}')

    flash(f'Status surat diubah menjadi {new_status}.', 'success')
    return redirect(url_for('surat.view_surat', id=id))


# ---------------------------------------------------------------------------
# Multi-Stage Approval (Flexible Chain)
# ---------------------------------------------------------------------------

@surat_bp.route('/surat/<int:id>/approve', methods=['POST'])
@login_required
def approve_surat(id):
    """Multi-stage approval with flexible chain based on urgency and settings."""
    from app.utils.approval_helpers import (
        get_approval_chain, is_stage_in_chain, check_delegation, log_audit, check_blacklist
    )

    stage = request.form.get('stage')
    decision = request.form.get('decision')
    note = request.form.get('note', '')

    conn = get_db()
    try:
        surat = query_one(conn, "SELECT * FROM surat_izin WHERE id=%s", (id,))
        if not surat:
            flash('Surat tidak ditemukan.', 'danger')
            return redirect(url_for('surat.surat_list'))

        # Check if stage is in the approval chain
        if not is_stage_in_chain(id, stage):
            flash(f'Stage {stage} tidak diperlukan untuk approval surat ini.', 'warning')
            return redirect(url_for('surat.view_surat', id=id))

        # Get role permissions for this stage
        stage_roles = {
            'user': ('user', 'admin', 'pemberi_kerja'),
            'satpam': ('satpam', 'admin'),
            'asman': ('asman', 'admin'),
            'manager': ('manager', 'admin'),
        }

        allowed_roles = stage_roles.get(stage, ())

        # Check delegation
        has_delegation, delegator_id, delegator_name = check_delegation(current_user.id, stage)

        if current_user.role not in allowed_roles and not has_delegation:
            abort(403)

        # If this is delegated approval, log it
        if has_delegation:
            log_audit(
                surat_id=id,
                user_id=current_user.id,
                action='DELEGATED_APPROVE',
                stage=stage,
                description=f'Menyetujui atas nama {delegator_name}',
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string,
                note=f'Delegasi dari {delegator_name}'
            )

        # Decision validation - user/satpam use sesuai/tidak_sesuai, asman/manager use approved/rejected
        user_decisions = ('sesuai', 'tidak_sesuai')
        admin_decisions = ('approved', 'rejected')

        if stage in ('user', 'satpam'):
            valid_decisions = user_decisions
        else:
            valid_decisions = admin_decisions

        if decision not in valid_decisions:
            flash('Keputusan tidak valid.', 'danger')
            return redirect(url_for('surat.view_surat', id=id))

        # Get approval chain for this surat
        chain = get_approval_chain(id)
        stage_order = ['user', 'satpam', 'asman', 'manager']

        # Check prerequisites - ensure previous stages in chain are completed
        for s in stage_order:
            if s == stage:
                break
            if s in chain:
                prev_status = surat.get(f'approval_{s}')
                # For user/satpam stages, accept 'sesuai' (approve items) - they can also reject with 'tidak_sesuai'
                # For asman/manager stages, only accept 'approved'
                if s in ('user', 'satpam'):
                    if prev_status not in ('sesuai', 'tidak_sesuai'):
                        flash(f'Sebelumnya harus diperiksa oleh {s.title()}.', 'warning')
                        return redirect(url_for('surat.view_surat', id=id))
                else:
                    if prev_status not in ('approved', 'rejected'):
                        flash(f'Sebelumnya harus direview oleh {s.title()}.', 'warning')
                        return redirect(url_for('surat.view_surat', id=id))

        # Get actual approver (either delegated or current user)
        actual_approver = delegator_id if has_delegation else current_user.id

        # Process approval based on stage
        if stage == 'user':
            # Parse barang items
            try:
                barang_items = json.loads(surat['barang_items']) if surat['barang_items'] else []
            except (json.JSONDecodeError, TypeError):
                barang_items = []

            # Check blacklist for each item (only block if decision is 'sesuai')
            if decision == 'sesuai':
                for item in barang_items:
                    nama_barang = item.get('nama_barang', '')
                    is_blacklisted, reason = check_blacklist(nama_barang)
                    if is_blacklisted:
                        flash(f'Barang "{nama_barang}" dalam blacklist: {reason}', 'danger')
                        return redirect(url_for('surat.view_surat', id=id))

            # Per-item approval - use correct index i
            for i, item in enumerate(barang_items):
                item_approval = request.form.get(f'item_user_approval_{i}', 'pending')
                item['approval_user'] = item_approval

            execute(conn, """UPDATE surat_izin SET
                approval_user=%s, approval_user_by=%s, approval_user_at=NOW(),
                approval_user_note=%s, barang_items=%s
                WHERE id=%s""",
                (decision, actual_approver, note, json.dumps(barang_items, ensure_ascii=False), id))

            label = 'Sesuai' if decision == 'sesuai' else 'Tidak Sesuai'
            log_activity(actual_approver, 'APPROVE', f'User/Pemberi Kerja: Surat #{id} → {label}')
            log_audit(id, actual_approver, 'APPROVE', 'user', f'Approved with decision: {decision}')

            # Notify creator if rejected
            if decision == 'tidak_sesuai' and surat.get('created_by'):
                notify_user(surat['created_by'], 'Barang Ditolak oleh User/Pemberi Kerja',
                            f'Surat {surat["no_surat"]}: Ada barang yang tidak sesuai: {note}',
                            f'/surat/{id}')

            # Notify satpam if sesuai (items approved)
            if decision == 'sesuai':
                satpams = query_all(conn, "SELECT id FROM users WHERE role IN ('satpam','admin') AND is_active=1")
                for s in satpams:
                    if s['id'] != current_user.id:
                        notify_user(s['id'], 'Perlu Pemeriksaan Satpam',
                                    f'Surat {surat["no_surat"]} sudah dicek User ({label}), perlu pemeriksaan',
                                    f'/surat/{id}')

        elif stage == 'satpam':
            # Satpam can review after user has made a decision (sesuai or tidak_sesuai)
            if surat.get('approval_user') == 'pending':
                flash('User/Pemberi Kerja belum memeriksa surat ini.', 'warning')
                return redirect(url_for('surat.view_surat', id=id))

            try:
                barang_items = json.loads(surat['barang_items']) if surat['barang_items'] else []
            except (json.JSONDecodeError, TypeError):
                barang_items = []

            # Per-item approval for satpam
            for i, item in enumerate(barang_items):
                item_approval = request.form.get(f'item_approval_{i}', 'pending')
                item['approval_satpam'] = item_approval

            # Determine new status based on decision
            # If tidak_sesuai, mark as rejected
            new_status = 'rejected' if decision == 'tidak_sesuai' else 'review'

            execute(conn, """UPDATE surat_izin SET
                approval_satpam=%s, approval_satpam_by=%s, approval_satpam_at=NOW(),
                approval_satpam_note=%s, barang_items=%s, status=%s
                WHERE id=%s""",
                (decision, actual_approver, note, json.dumps(barang_items, ensure_ascii=False), new_status, id))

            label = 'Sesuai' if decision == 'sesuai' else 'Tidak Sesuai'
            log_activity(actual_approver, 'APPROVE', f'Satpam: Surat #{id} → {label}')
            log_audit(id, actual_approver, 'APPROVE', 'satpam', f'Approved with decision: {decision}')

            # Notify creator if rejected
            if decision == 'tidak_sesuai' and surat.get('created_by'):
                notify_user(surat['created_by'], 'Surat Ditolak oleh Satpam',
                            f'Surat {surat["no_surat"]} ditolak oleh Satpam: {note}',
                            f'/surat/{id}')

            # Notify next approver based on chain
            if decision == 'sesuai':
                if 'asman' in chain:
                    asmans = query_all(conn, "SELECT id FROM users WHERE role IN ('asman','admin') AND is_active=1")
                    for a in asmans:
                        if a['id'] != current_user.id:
                            notify_user(a['id'], 'Perlu Review Asman',
                                        f'Surat {surat["no_surat"]} sudah diperiksa Satpam ({label})',
                                        f'/surat/{id}')
                elif 'manager' in chain:
                    managers = query_all(conn, "SELECT id FROM users WHERE role IN ('manager','admin') AND is_active=1")
                    for m in managers:
                        if m['id'] != current_user.id:
                            notify_user(m['id'], 'Perlu Approval Manager',
                                        f'Surat {surat["no_surat"]} sudah diperiksa Satpam ({label})',
                                        f'/surat/{id}')

        elif stage == 'asman':
            # Asman can only review after satpam has made a decision
            if surat.get('approval_satpam') == 'pending':
                flash('Satpam belum memeriksa surat ini.', 'warning')
                return redirect(url_for('surat.view_surat', id=id))

            execute(conn, """UPDATE surat_izin SET
                approval_asman=%s, approval_asman_by=%s, approval_asman_at=NOW(),
                approval_asman_note=%s
                WHERE id=%s""",
                (decision, actual_approver, note, id))

            label = 'Disetujui' if decision == 'approved' else 'Ditolak'
            log_activity(actual_approver, 'APPROVE', f'Asman: Surat #{id} → {label}')
            log_audit(id, actual_approver, 'APPROVE', 'asman', f'Review with decision: {decision}')

            if decision == 'approved':
                managers = query_all(conn, "SELECT id FROM users WHERE role IN ('manager','admin') AND is_active=1")
                for m in managers:
                    if m['id'] != current_user.id:
                        notify_user(m['id'], 'Perlu Approval Manager',
                                    f'Surat {surat["no_surat"]} sudah direview Asman ({label})',
                                    f'/surat/{id}')
            else:
                # Rejected by asman
                execute(conn, "UPDATE surat_izin SET status='rejected' WHERE id=%s", (id,))
                if surat.get('created_by'):
                    notify_user(surat['created_by'], 'Surat Ditolak',
                                f'Surat {surat["no_surat"]} ditolak oleh Asman',
                                f'/surat/{id}')

        elif stage == 'manager':
            # Manager can approve if asman in chain requires asman to approve first
            if 'asman' in chain and surat.get('approval_asman') == 'pending':
                flash('Asman belum mereview surat ini.', 'warning')
                return redirect(url_for('surat.view_surat', id=id))

            final_status = decision
            execute(conn, """UPDATE surat_izin SET
                approval_manager=%s, approval_manager_by=%s, approval_manager_at=NOW(),
                approval_manager_note=%s, status=%s
                WHERE id=%s""",
                (decision, actual_approver, note, final_status, id))

            label = 'Disetujui' if decision == 'approved' else 'Ditolak'
            log_activity(actual_approver, 'APPROVE', f'Manager: Surat #{id} → {label}')
            log_audit(id, actual_approver, 'APPROVE', 'manager', f'Final approval with decision: {decision}')

            # Notify creator
            if surat.get('created_by'):
                notify_user(surat['created_by'], 'Surat Final',
                            f'Surat {surat["no_surat"]} telah {label} oleh Manager',
                            f'/surat/{id}')

        else:
            flash('Stage tidak valid.', 'danger')
            return redirect(url_for('surat.view_surat', id=id))

        flash('Approval berhasil disimpan.', 'success')
        return redirect(url_for('surat.view_surat', id=id))

    except Exception as e:
        flash(f'Terjadi kesalahan: {str(e)}', 'danger')
        return redirect(url_for('surat.view_surat', id=id))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Delete Surat
# ---------------------------------------------------------------------------

@surat_bp.route('/surat/<int:id>/delete')
@login_required
@role_required('admin', 'manager')
def delete_surat(id):
    """Delete a surat izin."""
    conn = get_db()
    s = query_one(conn, "SELECT no_surat FROM surat_izin WHERE id=%s", (id,))
    if s:
        execute(conn, "DELETE FROM surat_izin WHERE id=%s", (id,))
        log_activity(current_user.id, 'DELETE', f'Surat {s["no_surat"]} dihapus')
        flash('Surat berhasil dihapus.', 'success')
    else:
        flash('Surat tidak ditemukan.', 'danger')
    conn.close()
    return redirect(url_for('surat.surat_list'))


# ---------------------------------------------------------------------------
# Export PDF
# ---------------------------------------------------------------------------

@surat_bp.route('/surat/<int:id>/pdf')
@login_required
def export_pdf(id):
    """Export a single surat as PDF."""
    conn = get_db()
    surat = query_one(conn, "SELECT * FROM surat_izin WHERE id=%s", (id,))
    if not surat:
        conn.close()
        flash('Surat tidak ditemukan.', 'danger')
        return redirect(url_for('surat.surat_list'))

    surat = dict(surat)
    try:
        surat['barang_items'] = json.loads(surat['barang_items'])
    except Exception:
        surat['barang_items'] = []
    surat['foto_list'] = parse_foto_list(surat.get('lampiran_foto'))

    # Look up approver names for the signature section
    for key in ('approval_user_by', 'approval_satpam_by', 'approval_asman_by', 'approval_manager_by'):
        uid = surat.get(key)
        if uid:
            u = query_one(conn, "SELECT nama_lengkap FROM users WHERE id=%s", (uid,))
            surat[key + '_name'] = u['nama_lengkap'] if u else '-'
        else:
            surat[key + '_name'] = ''

    creator_id = surat.get('created_by')
    if creator_id:
        creator = query_one(conn, "SELECT nama_lengkap FROM users WHERE id=%s", (creator_id,))
        surat['creator_name'] = creator['nama_lengkap'] if creator else '-'
    else:
        surat['creator_name'] = ''

    conn.close()

    # Build SPK download URL for the PDF link
    spk_url = None
    if surat.get('file_spk'):
        spk_url = request.host_url.rstrip('/') + url_for('static', filename='uploads/' + surat['file_spk'])

    # Generate QR Code for verification
    qr_code_url = f"{request.host_url}verify/{surat['id']}/{surat.get('unique_hash', '')}"
    qr_code_data_url = generate_qr_code(qr_code_url, size=120) if surat.get('unique_hash') else None

    # Convert logo to base64 data URL
    project_root = os.path.dirname(current_app.root_path)
    logo_path = os.path.join(project_root, 'static', 'images', 'logo.jpg')
    with open(logo_path, 'rb') as f:
        logo_data = base64.b64encode(f.read()).decode('utf-8')
    logo_data_url = f"data:image/jpeg;base64,{logo_data}"

    html = render_template('pdf_template.html', surat=surat,
                           upload_dir=os.path.abspath(Config.UPLOAD_DIR),
                           static_dir=os.path.abspath(os.path.join(project_root, 'static')),
                           logo_data_url=logo_data_url,
                           spk_url=spk_url,
                           qr_code_data_url=qr_code_data_url,
                           qr_code_url=qr_code_url,
                           now=datetime.now())
    try:
        from weasyprint import HTML
        from pathlib import Path
        base = Path(project_root, 'static').as_uri() + '/'
        pdf_bytes = HTML(string=html, base_url=base).write_pdf()
        clean = ''.join(c for c in surat['no_surat'] if c.isalnum() or c in '-_.')
        filename = f"surat_izin_{clean}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        flash(f'Gagal membuat PDF: {e}', 'danger')
        return redirect(url_for('surat.view_surat', id=id))


# ---------------------------------------------------------------------------
# API Endpoints for Professional Features
# ---------------------------------------------------------------------------

@surat_bp.route('/api/auto-no-surat')
@login_required
def auto_no_surat():
    """
    Generate automatic surat number.
    Format: YYYYMMDD-XXXX (daily increment)
    """
    today = datetime.now()
    date_str = today.strftime('%Y%m%d')

    conn = get_db()
    # Get the latest surat number for today
    row = query_one(conn, """
        SELECT no_surat FROM surat_izin
        WHERE DATE(created_at) = CURDATE()
        ORDER BY id DESC LIMIT 1
    """)
    conn.close()

    if row:
        # Extract the sequence number from existing surat
        import re
        match = re.search(r'(\d{8})-(\d+)', row['no_surat'])
        if match and match.group(1) == date_str:
            next_seq = int(match.group(2)) + 1
        else:
            next_seq = 1
    else:
        next_seq = 1

    # Format: YYYYMMDD-XXXX
    no_surat = f"{date_str}-{next_seq:04d}"

    return jsonify({
        'success': True,
        'no_surat': no_surat,
        'date': today.strftime('%Y-%m-%d'),
        'tgl_terbit': today.strftime('%Y-%m-%d')
    })


@surat_bp.route('/api/check-no-surat')
@login_required
def check_no_surat():
    """
    Check if surat number already exists.
    """
    no_surat = request.args.get('no_surat', '').strip()

    if not no_surat:
        return jsonify({'exists': False, 'message': ''})

    conn = get_db()
    row = query_one(conn, "SELECT id, no_surat FROM surat_izin WHERE no_surat=%s", (no_surat,))
    conn.close()

    if row:
        return jsonify({
            'exists': True,
            'message': f'No. Surat "{no_surat}" sudah terdaftar!',
            'id': row['id']
        })
    else:
        return jsonify({'exists': False, 'message': ''})


@surat_bp.route('/api/companies')
@login_required
def get_companies():
    """
    Get list of previously used companies for autocomplete.
    """
    conn = get_db()
    rows = query_all(conn, """
        SELECT DISTINCT perusahaan FROM surat_izin
        WHERE perusahaan IS NOT NULL AND perusahaan != ''
        ORDER BY perusahaan ASC
        LIMIT 20
    """)
    conn.close()

    companies = [row['perusahaan'] for row in rows]
    return jsonify({'success': True, 'companies': companies})


@surat_bp.route('/api/user-profile')
@login_required
def get_user_profile():
    """
    Get current user profile for auto-fill.
    """
    return jsonify({
        'success': True,
        'nama': current_user.nama_lengkap,
        'divisi': current_user.divisi or '',
        'username': current_user.username
    })


@surat_bp.route('/api/qrcode/<int:surat_id>')
def get_qr_code(surat_id):
    """
    Generate QR code for a surat.
    Returns base64 encoded PNG image.
    """
    conn = get_db()
    surat = query_one(conn, "SELECT id, unique_hash FROM surat_izin WHERE id=%s", (surat_id,))
    conn.close()

    if not surat or not surat.get('unique_hash'):
        return jsonify({'success': False, 'message': 'Surat tidak ditemukan'}), 404

    qr_code_url = f"{request.host_url}verify/{surat['id']}/{surat['unique_hash']}"
    qr_code_data_url = generate_qr_code(qr_code_url, size=200)

    return jsonify({
        'success': True,
        'qr_code': qr_code_data_url,
        'url': qr_code_url
    })


@surat_bp.route('/api/templates')
@login_required
def get_templates():
    """
    Get frequently used item templates.
    """
    # Common templates based on typical surat items
    templates = [
        {'nama_barang': 'Spare Part Mesin', 'satuan': 'Unit'},
        {'nama_barang': 'Tool Kit', 'satuan': 'Set'},
        {'nama_barang': 'oli Mesin', 'satuan': 'Liter'},
        {'nama_barang': 'Filter oli', 'satuan': 'Pcs'},
        {'nama_barang': 'Baut/Mur', 'satuan': 'Pcs'},
        {'nama_barang': 'Kabel Listrik', 'satuan': 'Meter'},
        {'nama_barang': 'Pipa HDPE', 'satuan': 'Meter'},
        {'nama_barang': 'Cat', 'satuan': 'Liter'},
        {'nama_barang': 'Gloves/Katrol', 'satuan': 'Pcs'},
        {'nama_barang': 'Sarung Tangan', 'satuan': 'Pcs'},
    ]
    return jsonify({'success': True, 'templates': templates})


@surat_bp.route('/api/save-draft', methods=['POST'])
@login_required
def save_draft():
    """
    Save form draft to localStorage (handled by client).
    This endpoint logs draft saves for analytics.
    """
    data = request.get_json() or {}
    form_data = json.dumps(data, ensure_ascii=False)

    # Log the draft save
    log_activity(current_user.id, 'DRAFT_SAVE', 'Saved surat draft')

    return jsonify({'success': True, 'message': 'Draft saved'})


@surat_bp.route('/api/recent-perusahaan')
@login_required
def get_recent_perusahaan():
    """
    Get recently used companies by current user.
    """
    conn = get_db()
    rows = query_all(conn, """
        SELECT DISTINCT perusahaan FROM surat_izin
        WHERE created_by=%s AND perusahaan IS NOT NULL AND perusahaan != ''
        ORDER BY created_at DESC
        LIMIT 10
    """, (current_user.id,))
    conn.close()

    companies = [row['perusahaan'] for row in rows]
    return jsonify({'success': True, 'companies': companies})


# ---------------------------------------------------------------------------
# Delegation API
# ---------------------------------------------------------------------------

@surat_bp.route('/api/delegations')
@login_required
def get_delegations():
    """Get active delegations for current user."""
    from app.utils.approval_helpers import get_active_delegations

    if not current_user.can_delegate():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    delegations = get_active_delegations(current_user.id)
    return jsonify({
        'success': True,
        'outgoing': delegations['outgoing'],
        'incoming': delegations['incoming']
    })


@surat_bp.route('/api/delegations', methods=['POST'])
@login_required
def create_delegation_api():
    """Create a new delegation."""
    from app.utils.approval_helpers import create_delegation as create_delegation_helper
    from app.utils.helpers import log_activity

    if not current_user.can_delegate():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    delegate_id = data.get('delegate_id')
    stages = data.get('stages', [])
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    reason = data.get('reason', '')

    if not all([delegate_id, stages, start_date, end_date]):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    try:
        sid = create_delegation_helper(
            delegator_id=current_user.id,
            delegate_id=delegate_id,
            stages=stages,
            start_date=start_date,
            end_date=end_date,
            reason=reason
        )
        log_activity(current_user.id, 'DELEGATE', f'Delegation created for stages: {stages}')
        return jsonify({'success': True, 'message': 'Delegation created', 'id': sid})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@surat_bp.route('/api/delegations/<int:delegation_id>', methods=['DELETE'])
@login_required
def revoke_delegation_api(delegation_id):
    """Revoke a delegation."""
    from app.utils.approval_helpers import revoke_delegation
    from app.utils.helpers import log_activity

    revoke_delegation(delegation_id, current_user.id)
    log_activity(current_user.id, 'REVOKE_DELEGATE', f'Delegation {delegation_id} revoked')
    return jsonify({'success': True, 'message': 'Delegation revoked'})


# ---------------------------------------------------------------------------
# Approval Chain API
# ---------------------------------------------------------------------------

@surat_bp.route('/api/approval-chain/<int:surat_id>')
@login_required
def get_surat_approval_chain(surat_id):
    """Get the approval chain for a specific surat."""
    from app.utils.approval_helpers import get_approval_chain, get_approval_progress

    conn = get_db()
    surat = query_one(conn, "SELECT * FROM surat_izin WHERE id=%s", (surat_id,))
    conn.close()

    if not surat:
        return jsonify({'success': False, 'message': 'Surat not found'}), 404

    chain = get_approval_chain(surat_id)
    progress = get_approval_progress(surat)

    return jsonify({
        'success': True,
        'chain': chain,
        'progress': {
            'completed': progress[0],
            'total': progress[1],
            'percentage': progress[2]
        }
    })


@surat_bp.route('/api/pending-approvals')
@login_required
def get_pending_approvals():
    """Get pending approvals for current user."""
    from app.utils.approval_helpers import check_pending_approvals_for_reminder, get_pending_count_by_role

    pending = check_pending_approvals_for_reminder(current_user.id)
    counts = get_pending_count_by_role()

    return jsonify({
        'success': True,
        'pending': pending,
        'counts': counts
    })


# ---------------------------------------------------------------------------
# Dashboard Statistics API
# ---------------------------------------------------------------------------

@surat_bp.route('/api/dashboard-stats')
@login_required
def get_dashboard_stats():
    """Get dashboard statistics."""
    conn = get_db()

    stats = {}

    # Total surat counts by status
    for status in ['pending', 'review', 'approved', 'rejected']:
        row = query_one(conn,
            "SELECT COUNT(*) as c FROM surat_izin WHERE status=%s", (status,))
        stats[f'total_{status}'] = row['c'] if row else 0

    # Total counts
    row = query_one(conn, "SELECT COUNT(*) as c FROM surat_izin")
    stats['total'] = row['c'] if row else 0

    # Monthly trend (last 6 months)
    monthly = query_all(conn, """
        SELECT DATE_FORMAT(created_at, '%Y-%m') as month, COUNT(*) as count
        FROM surat_izin
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(created_at, '%Y-%m')
        ORDER BY month DESC
    """)
    stats['monthly_trend'] = monthly

    # By division
    by_divisi = query_all(conn, """
        SELECT divisi, COUNT(*) as count
        FROM surat_izin
        GROUP BY divisi
        ORDER BY count DESC
        LIMIT 10
    """)
    stats['by_divisi'] = by_divisi

    # By type
    by_jenis = query_all(conn, """
        SELECT jenis, COUNT(*) as count
        FROM surat_izin
        GROUP BY jenis
    """)
    stats['by_jenis'] = {r['jenis']: r['count'] for r in by_jenis}

    # Overdue count
    row = query_one(conn, """
        SELECT COUNT(*) as c FROM surat_izin
        WHERE status IN ('pending', 'review')
          AND (approval_user = 'pending' OR approval_satpam = 'pending' OR
               approval_asman = 'pending' OR approval_manager = 'pending')
          AND created_at < DATE_SUB(NOW(), INTERVAL 24 HOUR)
    """)
    stats['overdue'] = row['c'] if row else 0

    conn.close()
    return jsonify({'success': True, 'stats': stats})


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

@surat_bp.route('/api/settings')
@login_required
def get_settings():
    """Get system settings (admin only)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    conn = get_db()
    settings = query_all(conn, "SELECT * FROM surat_settings ORDER BY setting_key")
    conn.close()

    return jsonify({'success': True, 'settings': settings})


@surat_bp.route('/api/settings', methods=['POST'])
@login_required
def update_setting():
    """Update a system setting (admin only)."""
    from app.utils.approval_helpers import set_setting
    from app.utils.helpers import log_activity

    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    key = data.get('key')
    value = data.get('value')

    if not key:
        return jsonify({'success': False, 'message': 'Key required'}), 400

    set_setting(key, value, current_user.id)
    log_activity(current_user.id, 'UPDATE_SETTING', f'Updated setting: {key}')

    return jsonify({'success': True, 'message': 'Setting updated'})


# ---------------------------------------------------------------------------
# Blacklist API
# ---------------------------------------------------------------------------

@surat_bp.route('/api/blacklist')
@login_required
def get_blacklist():
    """Get item blacklist (admin only)."""
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    conn = get_db()
    items = query_all(conn, "SELECT * FROM blacklist_items ORDER BY created_at DESC")
    conn.close()

    return jsonify({'success': True, 'items': items})


@surat_bp.route('/api/blacklist', methods=['POST'])
@login_required
def add_to_blacklist():
    """Add item to blacklist (admin only)."""
    from app.utils.helpers import log_activity

    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    data = request.get_json()
    item_name = data.get('item_name')
    pattern = data.get('pattern', '')
    reason = data.get('reason', '')

    if not item_name:
        return jsonify({'success': False, 'message': 'Item name required'}), 400

    conn = get_db()
    execute(conn, """
        INSERT INTO blacklist_items (item_name, item_pattern, reason, created_by)
        VALUES (%s, %s, %s, %s)
    """, (item_name, pattern, reason, current_user.id))
    conn.close()

    log_activity(current_user.id, 'BLACKLIST', f'Added to blacklist: {item_name}')
    return jsonify({'success': True, 'message': 'Item added to blacklist'})


# ---------------------------------------------------------------------------
# QR Code Verification
# ---------------------------------------------------------------------------

@surat_bp.route('/verify/<int:surat_id>/<hash>')
def verify_surat(surat_id, hash):
    """Public endpoint to verify surat authenticity via QR code."""
    from app.utils.approval_helpers import verify_surat_hash

    conn = get_db()
    surat = query_one(conn, """
        SELECT s.id, s.no_surat, s.jenis, s.tanggal, s.nama, s.perusahaan,
               s.status, s.approval_user, s.approval_satpam, s.approval_asman,
               s.approval_manager
        FROM surat_izin s
        WHERE s.id = %s
    """, (surat_id,))
    conn.close()

    if not surat:
        return render_template('error.html',
            error_title='Surat Tidak Ditemukan',
            error_message='Surat dengan ID tersebut tidak ditemukan.'), 404

    is_valid = verify_surat_hash(surat_id, hash)
    status_label = {
        'pending': 'Menunggu Persetujuan',
        'review': 'Sedang Direview',
        'approved': 'Disetujui',
        'rejected': 'Ditolak'
    }.get(surat['status'], surat['status'])

    return render_template('verify_surat.html',
        surat=surat,
        status_label=status_label,
        is_valid=is_valid,
        verify_hash=hash
    )


# ---------------------------------------------------------------------------
# Audit Trail API
# ---------------------------------------------------------------------------

@surat_bp.route('/api/audit-trail/<int:surat_id>')
@login_required
def get_audit_trail(surat_id):
    """Get audit trail for a surat (admin only)."""
    from app.utils.approval_helpers import get_audit_trail

    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    trail = get_audit_trail(surat_id)
    return jsonify({'success': True, 'trail': trail})


# ---------------------------------------------------------------------------
# Escalation API
# ---------------------------------------------------------------------------

@surat_bp.route('/api/escalate/<int:surat_id>')
@login_required
def escalate_surat_api(surat_id):
    """Manually escalate a surat (admin only)."""
    from app.utils.approval_helpers import escalate_surat, log_audit
    from app.utils.helpers import notify_admins

    if current_user.role not in ('admin', 'manager'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    escalate_surat(surat_id, escalation_level=1)

    conn = get_db()
    surat = query_one(conn, "SELECT no_surat FROM surat_izin WHERE id=%s", (surat_id,))
    conn.close()

    log_audit(surat_id, current_user.id, 'ESCALATE', description='Manual escalation')
    notify_admins(f'Surat {surat["no_surat"]} di-eskalasi oleh {current_user.nama_lengkap}',
                  f'/surat/{surat_id}', exclude_user=current_user.id)

    return jsonify({'success': True, 'message': 'Surat berhasil di-eskalasi'})
