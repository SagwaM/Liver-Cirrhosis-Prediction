# =============================================================
# app/routes/medic.py — Medic dashboard
# =============================================================
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from app.models import Patient, Prediction
from app import db
from sqlalchemy import func

medic = Blueprint('medic', __name__)

STAGE_LABELS = {1: ('Early', 'success'), 2: ('Moderate', 'warning'),
                3: ('Advanced', 'orange'), 4: ('End-stage', 'danger')}

DRUG_RECS = {
    1: {'primary': 'Ursodeoxycholic acid (UDCA) 13–15 mg/kg/day',
        'secondary': 'Vitamin E supplementation if NASH-related',
        'monitoring': 'LFTs every 6 months · FibroScan annually',
        'goal': 'Slow fibrosis progression, maintain liver function'},
    2: {'primary': 'Ursodeoxycholic acid (UDCA) 13–15 mg/kg/day',
        'secondary': 'Spironolactone 100mg/day if ascites · Beta-blockers for portal HTN',
        'monitoring': 'LFTs + ultrasound every 6 months · Endoscopy for varices',
        'goal': 'Manage portal hypertension, prevent decompensation'},
    3: {'primary': 'Spironolactone 100–400mg + Furosemide 40–160mg daily',
        'secondary': 'Propranolol/Carvedilol for variceal bleeding · Lactulose for encephalopathy',
        'monitoring': 'LFTs monthly · Renal function · Encephalopathy screening',
        'goal': 'Prevent and manage decompensation complications'},
    4: {'primary': 'Liver transplant evaluation — refer to transplant centre immediately',
        'secondary': 'Rifaximin 550mg twice daily · Albumin infusion for SBP',
        'monitoring': 'MELD score weekly · Immediate specialist review',
        'goal': 'Transplant listing or palliative care planning'},
}


def medic_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ['medic', 'admin']:
            flash('Medic access required.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


@medic.route('/medic_dashboard')
@login_required
@medic_required
def medic_dashboard():
    total      = Patient.query.count()
    reviews    = Prediction.query.filter_by(confidence_flag='REVIEW').count()
    alive      = Prediction.query.filter_by(predicted_status='C').count()
    deceased   = Prediction.query.filter_by(predicted_status='D').count()
    transplant = Prediction.query.filter_by(predicted_status='CL').count()

    # Stage breakdown
    stage_stats = {}
    for s in [1, 2, 3, 4]:
        total_s = Patient.query.filter_by(stage=s).count()
        alive_s = (Patient.query.join(Prediction)
                   .filter(Patient.stage == s, Prediction.predicted_status == 'C').count())
        dead_s  = (Patient.query.join(Prediction)
                   .filter(Patient.stage == s, Prediction.predicted_status == 'D').count())
        label, color = STAGE_LABELS[s]
        stage_stats[s] = {
            'total': total_s, 'alive': alive_s, 'deceased': dead_s,
            'label': label, 'color': color
        }

    flagged = (Patient.query.join(Prediction)
               .filter(Prediction.confidence_flag == 'REVIEW')
               .order_by(Patient.submitted_at.desc()).limit(5).all())

    recent  = (Patient.query.join(Prediction)
               .order_by(Patient.submitted_at.desc()).limit(8).all())

    return render_template('medic/medic_dashboard.html',
        total=total, reviews=reviews,
        alive=alive, deceased=deceased, transplant=transplant,
        stage_stats=stage_stats, flagged=flagged, recent=recent)


@medic.route('/patients')
@login_required
@medic_required
def patients():
    flag  = request.args.get('flag', '')
    query = Patient.query.join(Prediction)
    if flag == 'REVIEW':
        query = query.filter(Prediction.confidence_flag == 'REVIEW')
    elif flag in ['C', 'CL', 'D']:
        query = query.filter(Prediction.predicted_status == flag)
    all_patients = query.order_by(Patient.submitted_at.desc()).all()
    return render_template('medic/patients.html',
                           patients=all_patients, active_flag=flag)


@medic.route('/stage/<int:stage_num>')
@login_required
@medic_required
def stage_view(stage_num):
    if stage_num not in [1, 2, 3, 4]:
        flash('Invalid stage.', 'danger')
        return redirect(url_for('medic.medic_' \
        'dashboard'))

    label, color = STAGE_LABELS[stage_num]
    drug_rec     = DRUG_RECS[stage_num]

    # All patients at this stage
    patients_qs = (Patient.query.join(Prediction)
                   .filter(Patient.stage == stage_num)
                   .order_by(Patient.submitted_at.desc()).all())

    # Stats for this stage
    total_s  = len(patients_qs)
    alive_s  = sum(1 for p in patients_qs if p.prediction and p.prediction.predicted_status == 'C')
    dead_s   = sum(1 for p in patients_qs if p.prediction and p.prediction.predicted_status == 'D')
    trans_s  = sum(1 for p in patients_qs if p.prediction and p.prediction.predicted_status == 'CL')
    review_s = sum(1 for p in patients_qs if p.prediction and p.prediction.confidence_flag == 'REVIEW')

    avg_conf = (
        sum(p.prediction.confidence for p in patients_qs if p.prediction) / total_s
        if total_s > 0 else 0
    )

    return render_template('medic/stage_view.html',
        stage_num=stage_num, label=label, color=color,
        drug_rec=drug_rec, patients=patients_qs,
        total=total_s, alive=alive_s, deceased=dead_s,
        transplant=trans_s, reviews=review_s,
        avg_conf=round(avg_conf * 100, 1))


@medic.route('/summary')
@login_required
@medic_required
def summary():
    """Consolidated view — all stages with survival predictions and drug recommendations."""
    stage_data = []
    for s in [1, 2, 3, 4]:
        label, color = STAGE_LABELS[s]
        drug_rec     = DRUG_RECS[s]
        patients_qs  = (Patient.query.join(Prediction)
                        .filter(Patient.stage == s)
                        .order_by(Patient.submitted_at.desc()).all())
        total_s  = len(patients_qs)
        alive_s  = sum(1 for p in patients_qs if p.prediction and p.prediction.predicted_status == 'C')
        dead_s   = sum(1 for p in patients_qs if p.prediction and p.prediction.predicted_status == 'D')
        trans_s  = sum(1 for p in patients_qs if p.prediction and p.prediction.predicted_status == 'CL')
        review_s = sum(1 for p in patients_qs if p.prediction and p.prediction.confidence_flag == 'REVIEW')
        avg_conf = (sum(p.prediction.confidence for p in patients_qs if p.prediction) / total_s
                    if total_s > 0 else 0)
        stage_data.append({
            'stage': s, 'label': label, 'color': color,
            'drug_rec': drug_rec,
            'total': total_s, 'alive': alive_s,
            'deceased': dead_s, 'transplant': trans_s,
            'reviews': review_s,
            'avg_conf': round(avg_conf * 100, 1),
            'survival_rate': round(alive_s / total_s * 100, 1) if total_s > 0 else 0,
        })
    return render_template('medic/summary.html', stage_data=stage_data)


@medic.route('/patient/<int:patient_id>')
@login_required
@medic_required
def patient_detail(patient_id):
    patient    = Patient.query.get_or_404(patient_id)
    prediction = Prediction.query.filter_by(patient_id=patient_id).first_or_404()
    label, color = STAGE_LABELS.get(patient.stage, ('Unknown', 'secondary'))
    status_colors = {'C': 'success', 'CL': 'warning', 'D': 'danger'}
    status_color  = status_colors.get(prediction.predicted_status, 'secondary')
    return render_template('medic/patient_detail.html',
        patient=patient, prediction=prediction,
        stage_label=label, stage_color=color, status_color=status_color)
