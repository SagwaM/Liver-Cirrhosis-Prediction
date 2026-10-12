# =============================================================
# app/routes/lab.py — Lab Technician dashboard
# =============================================================
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import Patient, Prediction
from app.utils.predict import predict_patient

lab = Blueprint('lab', __name__)


def lab_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['lab', 'admin']:
            flash('Lab technician access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@lab.route('/lab_dashboard')
@login_required
@lab_required
def lab_dashboard():
    # Show only patients submitted by this lab tech
    my_patients = (Patient.query
                  .filter_by(submitted_by=current_user.id)
                  .order_by(Patient.submitted_at.desc())
                  .limit(10)
                  .all())
    total = Patient.query.filter_by(submitted_by=current_user.id).count()
    return render_template('lab/lab_dashboard.html',
                           recent_patients=my_patients,
                           total=total)


@lab.route('/submit', methods=['GET', 'POST'])
@login_required
@lab_required
def submit():
    if request.method == 'POST':
        # ── Validate required fields ──────────────────────────
        required = ['patient_name', 'age', 'sex', 'bilirubin',
                    'prothrombin', 'copper', 'hepatomegaly',
                    'stage', 'sgot', 'spiders']

        for field in required:
            if not request.form.get(field):
                flash(f'Field "{field}" is required.', 'danger')
                return render_template('lab/submit.html')

        try:
            # ── Save patient record ───────────────────────────
            patient = Patient(
                patient_name = request.form['patient_name'].strip(),
                age          = float(request.form['age']),
                sex          = request.form['sex'],
                bilirubin    = float(request.form['bilirubin']),
                prothrombin  = float(request.form['prothrombin']),
                copper       = float(request.form['copper']),
                hepatomegaly = int(request.form['hepatomegaly']),
                stage        = int(request.form['stage']),
                sgot         = float(request.form['sgot']),
                spiders      = int(request.form['spiders']),
                submitted_by = current_user.id
            )
            db.session.add(patient)
            db.session.flush()   # get patient.id before committing

            # ── Run prediction ────────────────────────────────
            result = predict_patient(request.form)

            # ── Save prediction ───────────────────────────────
            prediction = Prediction(
                patient_id        = patient.id,
                reviewed_by       = current_user.username,
                predicted_status  = result['predicted_status'],
                predicted_outcome = result['predicted_outcome'],
                prob_alive        = result['prob_alive'],
                prob_transplant   = result['prob_transplant'],
                prob_deceased     = result['prob_deceased'],
                confidence        = result['confidence'],
                confidence_flag   = result['confidence_flag'],
                primary_drug      = result['primary_drug'],
                secondary_drug    = result['secondary_drug'],
                monitoring        = result['monitoring'],
                treatment_goal    = result['treatment_goal'],
                clinical_note     = result['clinical_note'],
            )
            db.session.add(prediction)
            db.session.commit()

            flash(f'Patient "{patient.patient_name}" submitted successfully. '
                  f'Prediction is ready for the medic.', 'success')
            return redirect(url_for('lab.lab_confirmation', patient_id=patient.id))

        except ValueError as e:
            db.session.rollback()
            flash(f'Invalid input value: {e}', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing submission: {e}', 'danger')

    return render_template('lab/submit.html')


@lab.route('/lab-confirmation/<int:patient_id>')
@login_required
@lab_required
def lab_confirmation(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return render_template('lab/confirmation.html', patient=patient)
