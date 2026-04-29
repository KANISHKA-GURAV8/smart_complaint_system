from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Complaint(db.Model):
    __tablename__ = 'complaints'

    id = db.Column(db.String(20), primary_key=True)
    original_text = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(10), default='en')
    translated_text = db.Column(db.Text)
    formal_letter = db.Column(db.Text)
    location_lat = db.Column(db.Float)
    location_lon = db.Column(db.Float)
    location_name = db.Column(db.String(500))
    is_emergency = db.Column(db.Boolean, default=False)
    is_anonymous = db.Column(db.Boolean, default=True)
    user_name = db.Column(db.String(200), default='')
    user_contact = db.Column(db.String(100), default='')
    proof_images = db.Column(db.Text, default='[]')       # JSON list of filenames
    status = db.Column(db.String(50), default='received') # received|assigned|in_progress|resolved
    assigned_to = db.Column(db.String(200), default='')
    response_submitted = db.Column(db.Boolean, default=False)
    work_completed = db.Column(db.Boolean, default=False)
    resolution_images = db.Column(db.Text, default='[]')  # JSON list of filenames
    blockchain_hash = db.Column(db.String(64), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BlockchainLog(db.Model):
    __tablename__ = 'blockchain_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    complaint_id = db.Column(db.String(20), db.ForeignKey('complaints.id'), nullable=True)
    action = db.Column(db.String(100))
    data = db.Column(db.Text)           # JSON string
    block_hash = db.Column(db.String(64))
    previous_hash = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
