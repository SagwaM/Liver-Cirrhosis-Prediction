# =============================================================
# app/models.py — SQLite database models
# =============================================================
from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    """System users — admin, lab technician, medic."""
    __tablename__ = 'users'

    id         = db.Column(db.Integer,  primary_key=True)
    username   = db.Column(db.String(80),  unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)
    role       = db.Column(db.String(20),  nullable=False)   # admin | lab | medic
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)
    is_active  = db.Column(db.Boolean,     default=True)

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Patient(db.Model):
    """Patient lab values submitted by the lab technician."""
    __tablename__ = 'patients'

    id           = db.Column(db.Integer, primary_key=True)
    patient_name = db.Column(db.String(120), nullable=False)
    age          = db.Column(db.Float,   nullable=False)
    sex          = db.Column(db.String(1),   nullable=False)
    bilirubin    = db.Column(db.Float,   nullable=False)
    prothrombin  = db.Column(db.Float,   nullable=False)
    copper       = db.Column(db.Float,   nullable=False)
    hepatomegaly = db.Column(db.Integer, nullable=False)
    stage        = db.Column(db.Integer, nullable=False)
    sgot         = db.Column(db.Float,   nullable=False)
    spiders      = db.Column(db.Integer, nullable=False)
    submitted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to prediction and submitting user
    prediction   = db.relationship('Prediction', backref='patient',
                                   uselist=False, lazy=True)
    submitter    = db.relationship('User', foreign_keys=[submitted_by])

    def __repr__(self):
        return f'<Patient {self.patient_name}>'


class Prediction(db.Model):
    """Model prediction and drug recommendation for a patient."""
    __tablename__ = 'predictions'

    id                = db.Column(db.Integer, primary_key=True)
    patient_id        = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)

    # Who reviewed / is responsible — medic username stored at prediction time
    reviewed_by       = db.Column(db.String(80), nullable=True)

    # Survival prediction
    predicted_status  = db.Column(db.String(5))
    predicted_outcome = db.Column(db.String(50))
    prob_alive        = db.Column(db.Float)
    prob_transplant   = db.Column(db.Float)
    prob_deceased     = db.Column(db.Float)
    confidence        = db.Column(db.Float)
    confidence_flag   = db.Column(db.String(10))

    # Drug recommendation (from entered Stage)
    primary_drug      = db.Column(db.Text)
    secondary_drug    = db.Column(db.Text)
    monitoring        = db.Column(db.Text)
    treatment_goal    = db.Column(db.Text)
    clinical_note     = db.Column(db.Text)

    predicted_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Prediction patient={self.patient_id} status={self.predicted_status}>'
