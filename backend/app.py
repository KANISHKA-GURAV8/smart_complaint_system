import os
import uuid
import json
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

# ── App setup ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, '..', 'frontend')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4'}

os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(
    __name__,
    static_folder=os.path.join(FRONTEND_DIR, 'static'),
    static_url_path='/static'
)
app.secret_key = os.getenv('SECRET_KEY', 'grievance-secret-2024')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MB

# ── Database: PostgreSQL on Render, SQLite locally ─────────────────────────────
_db_url = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'complaints.db')}")
# Render gives postgres:// but SQLAlchemy requires postgresql://
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


CORS(app, supports_credentials=True)

from models import db, Complaint, BlockchainLog
from blockchain_log import add_block, verify_chain
from ai_engine import translate_to_english, generate_formal_letter

db.init_app(app)
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')

# In-memory OTP store: { phone: {otp, name, expires_at} }
_otp_store: dict = {}


# ── Helpers ────────────────────────────────────────────────────────────────────
def allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def new_complaint_id():
    return 'CMP-' + uuid.uuid4().hex[:6].upper()


def save_files(file_list, prefix=''):
    paths = []
    for f in file_list:
        if f and allowed(f.filename):
            name = prefix + uuid.uuid4().hex[:8] + '_' + secure_filename(f.filename)
            f.save(os.path.join(UPLOAD_DIR, name))
            paths.append(name)
    return paths


# ── Frontend page routes ───────────────────────────────────────────────────────
@app.route('/')
def page_index():
    return send_from_directory(FRONTEND_DIR, 'index.html')

@app.route('/submit')
def page_submit():
    return send_from_directory(FRONTEND_DIR, 'submit.html')

@app.route('/track')
def page_track():
    return send_from_directory(FRONTEND_DIR, 'track.html')

# ── PWA files served from root (required for service worker scope) ─────────────
@app.route('/sw.js')
def pwa_sw():
    resp = send_from_directory(os.path.join(FRONTEND_DIR, 'static'), 'sw.js')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

@app.route('/manifest.json')
def pwa_manifest():
    return send_from_directory(os.path.join(FRONTEND_DIR, 'static'), 'manifest.json')

@app.route('/login')
def page_user_login():
    return send_from_directory(FRONTEND_DIR, 'user_login.html')

@app.route('/admin')
@app.route('/admin/')
def page_admin_login():
    return send_from_directory(os.path.join(FRONTEND_DIR, 'admin'), 'login.html')

@app.route('/admin/dashboard')
def page_admin_dashboard():
    return send_from_directory(os.path.join(FRONTEND_DIR, 'admin'), 'dashboard.html')

@app.route('/admin/complaint/<complaint_id>')
def page_admin_detail(complaint_id):
    return send_from_directory(os.path.join(FRONTEND_DIR, 'admin'), 'complaint_detail.html')

# Serve uploaded proof/resolution images
@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ── Email OTP helper ───────────────────────────────────────────────────────
def _send_otp_email(to_email: str, name: str, otp: str) -> None:
    """
    Send OTP via Gmail SMTP.
    Requires EMAIL_ADDRESS and EMAIL_APP_PASSWORD in .env.
    Raises an exception with a descriptive message if sending fails.
    """
    sender   = os.getenv('EMAIL_ADDRESS', '').strip()
    password = os.getenv('EMAIL_APP_PASSWORD', '').replace(' ', '').strip()  # remove spaces
    if not sender or not password:
        raise RuntimeError(
            'Email not configured. Add EMAIL_ADDRESS and EMAIL_APP_PASSWORD to backend/.env'
        )

    html_body = f"""
    <div style="font-family:'Segoe UI',Arial,sans-serif;max-width:480px;margin:auto;background:#0e0e1a;color:#f0f0ff;border-radius:16px;overflow:hidden;">
      <div style="background:linear-gradient(135deg,#6C63FF,#FF6B9D);padding:28px 32px;text-align:center;">
        <h1 style="margin:0;font-size:1.6rem;color:#fff;">&#128226; Awaaz</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,.85);font-size:.9rem;">Smart Grievance Redressal Platform</p>
      </div>
      <div style="padding:32px;">
        <p style="font-size:1rem;margin-top:0;">Hello <strong>{name}</strong>,</p>
        <p style="color:#a0a0c0;">Your one-time password (OTP) to login to Awaaz is:</p>
        <div style="text-align:center;margin:24px 0;">
          <div style="display:inline-block;background:rgba(108,99,255,0.15);border:2px solid rgba(108,99,255,0.4);
                      border-radius:12px;padding:16px 28px;">
            <span style="font-size:2.8rem;font-weight:800;letter-spacing:.5em;
                         font-family:'Courier New',monospace;color:#a78bfa;">{otp}</span>
          </div>
        </div>
        <p style="font-size:.85rem;color:#606080;text-align:center;">
          This OTP is valid for <strong style='color:#a78bfa;'>5 minutes</strong>.<br>
          Do not share it with anyone.
        </p>
        <hr style="border:none;border-top:1px solid rgba(255,255,255,.08);margin:24px 0;"/>
        <p style="font-size:.78rem;color:#404060;margin:0;">
          If you didn't request this OTP, please ignore this email.
          This is an automated message from the Awaaz Grievance Redressal Platform.
        </p>
      </div>
    </div>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'[Awaaz] Your OTP: {otp}'
    msg['From']    = f'Awaaz Platform <{sender}>'
    msg['To']      = to_email
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as server:
            server.login(sender, password)
            server.sendmail(sender, to_email, msg.as_string())
        print(f'[EMAIL] OTP sent to {to_email}')
    except smtplib.SMTPAuthenticationError:
        raise RuntimeError(
            'Gmail authentication failed. Make sure:\n'
            '1. 2-Step Verification is ON in your Google account\n'
            '2. EMAIL_APP_PASSWORD is a valid App Password (not your regular Gmail password)\n'
            '3. Generate one at: myaccount.google.com/apppasswords'
        )
    except smtplib.SMTPException as e:
        raise RuntimeError(f'SMTP error: {e}')
    except Exception as e:
        raise RuntimeError(f'Failed to send email: {e}')


# ── API: User OTP login ────────────────────────────────────────────────────────
@app.route('/api/user/send-otp', methods=['POST'])
def api_send_otp():
    data  = request.get_json(force=True)
    email = data.get('email', '').strip().lower()
    name  = data.get('name', '').strip()
    if not email or not name:
        return jsonify({'error': 'Name and email are required'}), 400
    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'error': 'Invalid email address'}), 400

    otp = ''.join(random.choices(string.digits, k=6))
    _otp_store[email] = {
        'otp': otp,
        'name': name,
        'expires_at': datetime.utcnow() + timedelta(minutes=5)
    }

    try:
        _send_otp_email(email, name, otp)
        return jsonify({'success': True, 'email_sent': True})
    except RuntimeError as e:
        # Remove OTP from store since we couldn't deliver it
        _otp_store.pop(email, None)
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/verify-otp', methods=['POST'])
def api_verify_otp():
    data  = request.get_json(force=True)
    email = data.get('email', '').strip().lower()
    otp   = data.get('otp', '').strip()
    record = _otp_store.get(email)
    if not record:
        return jsonify({'error': 'No OTP sent to this email'}), 400
    if datetime.utcnow() > record['expires_at']:
        _otp_store.pop(email, None)
        return jsonify({'error': 'OTP has expired. Please request a new one.'}), 400
    if record['otp'] != otp:
        return jsonify({'error': 'Incorrect OTP. Please try again.'}), 400
    _otp_store.pop(email, None)
    session['user_email'] = email
    session['user_name']  = record['name']
    return jsonify({'success': True, 'name': record['name'], 'email': email})


@app.route('/api/user/me', methods=['GET'])
def api_user_me():
    if session.get('user_email'):
        return jsonify({'logged_in': True,
                        'name':  session['user_name'],
                        'email': session['user_email']})
    return jsonify({'logged_in': False})


@app.route('/api/user/logout', methods=['POST'])
def api_user_logout():
    session.pop('user_email', None)
    session.pop('user_name', None)
    return jsonify({'success': True})


# ── API: Submit complaint ──────────────────────────────────────────────────────
@app.route('/api/submit', methods=['POST'])
def api_submit():
    try:
        f = request.form
        original_text = f.get('text', '').strip()
        if not original_text:
            return jsonify({'error': 'Complaint text is required'}), 400

        language      = f.get('language', 'en')
        is_emergency  = f.get('is_emergency', 'false').lower() == 'true'
        is_anonymous  = f.get('is_anonymous', 'true').lower() == 'true'
        # If not anonymous and user is logged in via OTP, use session identity
        if not is_anonymous and session.get('user_email'):
            user_name    = session.get('user_name', f.get('user_name', ''))
            user_contact = session.get('user_email', f.get('user_contact', ''))  # email as contact
        elif not is_anonymous:
            user_name    = f.get('user_name', '')
            user_contact = f.get('user_contact', '')
        else:
            user_name    = ''
            user_contact = ''
        loc_lat       = f.get('location_lat', '')
        loc_lon       = f.get('location_lon', '')
        loc_name      = f.get('location_name', 'Location not provided')

        translated    = translate_to_english(original_text, language)
        formal_letter = generate_formal_letter(translated, loc_name, is_emergency)
        proof_images  = save_files(request.files.getlist('proof_images'))
        cid           = new_complaint_id()

        complaint = Complaint(
            id=cid,
            original_text=original_text,
            language=language,
            translated_text=translated,
            formal_letter=formal_letter,
            location_lat=float(loc_lat) if loc_lat else None,
            location_lon=float(loc_lon) if loc_lon else None,
            location_name=loc_name,
            is_emergency=is_emergency,
            is_anonymous=is_anonymous,
            user_name=user_name,
            user_contact=user_contact,
            proof_images=json.dumps(proof_images),
            status='received',
            resolution_images='[]'
        )
        db.session.add(complaint)
        db.session.commit()

        block_hash = add_block(cid, 'COMPLAINT_SUBMITTED', {
            'status': 'received', 'is_emergency': is_emergency,
            'timestamp': datetime.utcnow().isoformat()
        })
        complaint.blockchain_hash = block_hash
        db.session.commit()

        return jsonify({'success': True, 'complaint_id': cid, 'blockchain_hash': block_hash})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── API: Public track ──────────────────────────────────────────────────────────
@app.route('/api/track/<complaint_id>', methods=['GET'])
def api_track(complaint_id):
    c = Complaint.query.get(complaint_id.upper())
    if not c:
        return jsonify({'error': 'Complaint not found'}), 404

    logs = BlockchainLog.query.filter_by(complaint_id=c.id).order_by(BlockchainLog.timestamp).all()
    return jsonify({
        'id': c.id,
        'status': c.status,
        'is_emergency': c.is_emergency,
        'location_name': c.location_name,
        'created_at': c.created_at.isoformat(),
        'assigned_to': c.assigned_to,
        'resolution_images': json.loads(c.resolution_images or '[]'),
        'response_submitted': c.response_submitted,
        'work_completed': c.work_completed,
        'blockchain_hash': c.blockchain_hash,
        'formal_letter': c.formal_letter,
        'logs': [{'action': l.action, 'timestamp': l.timestamp.isoformat(),
                  'block_hash': l.block_hash} for l in logs]
    })


# ── API: Admin login ───────────────────────────────────────────────────────────
@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    data = request.get_json(force=True)
    if data.get('password') == ADMIN_PASSWORD:
        session['admin'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid password'}), 401

@app.route('/api/admin/logout', methods=['POST'])
def api_admin_logout():
    session.pop('admin', None)
    return jsonify({'success': True})


# ── API: Admin list ────────────────────────────────────────────────────────────
@app.route('/api/admin/complaints', methods=['GET'])
def api_admin_list():
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    status_f    = request.args.get('status', '')
    emergency_f = request.args.get('emergency', 'false').lower() == 'true'
    q = Complaint.query
    if status_f:   q = q.filter_by(status=status_f)
    if emergency_f: q = q.filter_by(is_emergency=True)
    complaints = q.order_by(Complaint.is_emergency.desc(), Complaint.created_at.desc()).all()

    return jsonify([{
        'id': c.id, 'status': c.status, 'is_emergency': c.is_emergency,
        'location_name': c.location_name, 'created_at': c.created_at.isoformat(),
        'language': c.language, 'assigned_to': c.assigned_to,
        'response_submitted': c.response_submitted, 'work_completed': c.work_completed
    } for c in complaints])


# ── API: Admin get single complaint ───────────────────────────────────────────
@app.route('/api/admin/complaint/<complaint_id>', methods=['GET'])
def api_admin_get(complaint_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    c = Complaint.query.get(complaint_id.upper())
    if not c:
        return jsonify({'error': 'Complaint not found'}), 404

    logs = BlockchainLog.query.filter_by(complaint_id=c.id).order_by(BlockchainLog.timestamp).all()
    return jsonify({
        'id': c.id, 'original_text': c.original_text, 'language': c.language,
        'translated_text': c.translated_text, 'formal_letter': c.formal_letter,
        'location_lat': c.location_lat, 'location_lon': c.location_lon,
        'location_name': c.location_name, 'is_emergency': c.is_emergency,
        'is_anonymous': c.is_anonymous,
        'user_name':    c.user_name    if not c.is_anonymous else '[Anonymous]',
        'user_contact': c.user_contact if not c.is_anonymous else '[Hidden for privacy]',
        'proof_images': json.loads(c.proof_images or '[]'),
        'status': c.status, 'assigned_to': c.assigned_to,
        'response_submitted': c.response_submitted, 'work_completed': c.work_completed,
        'resolution_images': json.loads(c.resolution_images or '[]'),
        'created_at': c.created_at.isoformat(), 'blockchain_hash': c.blockchain_hash,
        'logs': [{'action': l.action, 'timestamp': l.timestamp.isoformat(),
                  'block_hash': l.block_hash} for l in logs]
    })


# ── API: Admin update complaint ────────────────────────────────────────────────
@app.route('/api/admin/update/<complaint_id>', methods=['POST'])
def api_admin_update(complaint_id):
    if not session.get('admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    c = Complaint.query.get(complaint_id.upper())
    if not c:
        return jsonify({'error': 'Complaint not found'}), 404

    f          = request.form
    new_status = f.get('status', c.status)
    old_status = c.status

    c.status             = new_status
    c.response_submitted = f.get('response_submitted', str(c.response_submitted)).lower() == 'true'
    c.work_completed     = f.get('work_completed', str(c.work_completed)).lower() == 'true'
    c.assigned_to        = f.get('assigned_to', c.assigned_to or '')

    res_images = json.loads(c.resolution_images or '[]')
    res_images += save_files(request.files.getlist('resolution_images'), prefix='res_')
    c.resolution_images = json.dumps(res_images)
    db.session.commit()

    if old_status != new_status:
        add_block(c.id, f'STATUS_{new_status.upper()}', {
            'old': old_status, 'new': new_status,
            'timestamp': datetime.utcnow().isoformat()
        })

    return jsonify({'success': True})


# ── API: Utility ───────────────────────────────────────────────────────────────
@app.route('/api/verify-chain')
def api_verify():
    valid, msg = verify_chain()
    return jsonify({'valid': valid, 'message': msg})


@app.route('/api/stats')
def api_stats():
    total      = Complaint.query.count()
    emergency  = Complaint.query.filter_by(is_emergency=True).count()
    resolved   = Complaint.query.filter_by(status='resolved').count()
    in_prog    = Complaint.query.filter(Complaint.status.in_(['assigned', 'in_progress'])).count()
    return jsonify({'total': total, 'emergency': emergency,
                    'resolved': resolved, 'in_progress': in_prog})


# ── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("[OK] Database initialised")
    app.run(debug=True, host='0.0.0.0', port=5000)
