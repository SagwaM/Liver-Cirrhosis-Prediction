# =============================================================
# app/routes/admin.py — Admin dashboard
# =============================================================
from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps
from app import db
from app.models import User, Patient, Prediction
import csv, io
from datetime import datetime

admin = Blueprint('admin', __name__)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@admin.route('/admin_dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_patients   = Patient.query.count()
    total_predictions = Prediction.query.count()
    total_users      = User.query.count()
    review_flags     = Prediction.query.filter_by(confidence_flag='REVIEW').count()

    # Status breakdown
    status_counts = {
        'Alive (C)'      : Prediction.query.filter_by(predicted_status='C').count(),
        'Transplant (CL)': Prediction.query.filter_by(predicted_status='CL').count(),
        'Deceased (D)'   : Prediction.query.filter_by(predicted_status='D').count(),
    }

    recent = (Patient.query
              .join(Prediction)
              .order_by(Patient.submitted_at.desc())
              .limit(10)
              .all())
    return render_template('admin/admin_dashboard.html',
        total_patients=total_patients,
        total_predictions=total_predictions,
        total_users=total_users,
        review_flags=review_flags,
        status_counts=status_counts,
        recent=recent
    )


@admin.route('/patients')
@login_required
@admin_required
def patients():
    all_patients = (Patient.query
                   .order_by(Patient.submitted_at.desc())
                   .all())
    return render_template('admin/patients.html', patients=all_patients)


@admin.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role     = request.form.get('role', '')

        if not all([username, password, role]):
            flash('All fields are required.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash(f'Username "{username}" already exists.', 'danger')
        elif role not in ['admin', 'lab', 'medic']:
            flash('Invalid role selected.', 'danger')
        else:
            user = User(username=username,
                       password=generate_password_hash(password),
                       role=role)
            db.session.add(user)
            db.session.commit()
            flash(f'User "{username}" ({role}) created successfully.', 'success')
            return redirect(url_for('admin.users'))

    return render_template('admin/add_user.html')


@admin.route('/users/toggle/<int:user_id>')
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User "{user.username}" {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/patient/<int:patient_id>')
@login_required
@admin_required
def patient_detail(patient_id):
    from app.models import Prediction
    patient    = Patient.query.get_or_404(patient_id)
    prediction = Prediction.query.filter_by(patient_id=patient_id).first()
    return render_template('admin/patient_detail.html',
                           patient=patient, prediction=prediction)


@admin.route('/export')
@login_required
@admin_required
def export_csv():
    """Export all predictions as CSV download."""
    patients = (Patient.query
               .join(Prediction)
               .order_by(Patient.submitted_at.desc())
               .all())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Patient Name', 'Age', 'Sex', 'Stage',
        'Bilirubin', 'Prothrombin', 'Copper', 'SGOT', 'Spiders', 'Hepatomegaly',
        'Predicted Status', 'Predicted Outcome', 'Confidence',
        'P(Alive)', 'P(Transplant)', 'P(Deceased)', 'Confidence Flag',
        'Primary Drug', 'Secondary Drug', 'Monitoring', 'Submitted At'
    ])

    for p in patients:
        pred = p.prediction
        writer.writerow([
            p.patient_name, p.age, p.sex, p.stage,
            p.bilirubin, p.prothrombin, p.copper, p.sgot, p.spiders, p.hepatomegaly,
            pred.predicted_status if pred else '',
            pred.predicted_outcome if pred else '',
            pred.confidence if pred else '',
            pred.prob_alive if pred else '',
            pred.prob_transplant if pred else '',
            pred.prob_deceased if pred else '',
            pred.confidence_flag if pred else '',
            pred.primary_drug if pred else '',
            pred.secondary_drug if pred else '',
            pred.monitoring if pred else '',
            p.submitted_at.strftime('%Y-%m-%d %H:%M')
        ])

    output.seek(0)
    filename = f"cirrhosis_predictions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
