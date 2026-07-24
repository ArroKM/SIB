"""
Validators and file upload utilities.
"""
import os
import uuid

from app.config import Config


def save_uploaded_file(file_obj, allowed_ext=None):
    """
    Save an uploaded file to the upload directory.

    Args:
        file_obj: FileStorage object from Flask request.files
        allowed_ext: Set of allowed extensions (defaults to Config.ALLOWED_EXTENSIONS)

    Returns:
        The saved filename if successful, None otherwise.
    """
    if allowed_ext is None:
        allowed_ext = Config.ALLOWED_EXTENSIONS

    if not file_obj or not file_obj.filename:
        return None

    if '.' not in file_obj.filename:
        return None

    ext = file_obj.filename.rsplit('.', 1)[1].lower()
    if ext not in allowed_ext:
        return None

    filename = f"{uuid.uuid4().hex}.{ext}"
    file_obj.save(os.path.join(Config.UPLOAD_DIR, filename))
    return filename


def save_barang_fotos(file_list, index):
    """
    Save multiple photos for a barang item.

    Args:
        file_list: List of FileStorage objects
        index: The barang item index (for logging/debugging)

    Returns:
        List of saved filenames.
    """
    saved_names = []
    for foto in file_list:
        if foto and foto.filename and '.' in foto.filename:
            ext = foto.filename.rsplit('.', 1)[1].lower()
            if ext in Config.ALLOWED_EXTENSIONS:
                fname = f"{uuid.uuid4().hex}.{ext}"
                foto.save(os.path.join(Config.UPLOAD_DIR, fname))
                saved_names.append(fname)
    return saved_names


def validate_required_fields(form_data, required_fields):
    """
    Validate that all required fields are present and non-empty.

    Args:
        form_data: The form data dictionary
        required_fields: List of required field names

    Returns:
        List of missing field names (empty if all present)
    """
    missing = []
    for field in required_fields:
        if not form_data.get(field):
            missing.append(field)
    return missing
