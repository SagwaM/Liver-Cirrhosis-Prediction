# =============================================================
# app/utils/predict.py — Preprocessing + prediction pipeline
#
# This is the bridge between raw lab tech input and the ML model.
# It applies the EXACT same preprocessing steps as Notebook 02
# so the model always receives correctly formatted input.
# =============================================================
import os
import joblib
import numpy as np
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MODEL_PATH      = os.path.join(BASE_DIR, 'models', 'model.pkl')
SCALER_PATH     = os.path.join(BASE_DIR, 'models', 'scaler.pkl')
FEATURES_PATH   = os.path.join(BASE_DIR, 'models', 'selected_features.pkl')

# ── Load artefacts once at module import (not on every request) ─
model             = joblib.load(MODEL_PATH)
scaler            = joblib.load(SCALER_PATH)
SELECTED_FEATURES = joblib.load(FEATURES_PATH)

# ── Label maps ─────────────────────────────────────────────────
CLASS_MAP   = {0: 'C', 1: 'CL', 2: 'D'}
OUTCOME_MAP = {
    'C' : 'Alive / Censored',
    'CL': 'Liver Transplant',
    'D' : 'Deceased'
}

# ── Drug recommendations by Stage ──────────────────────────────
# Evidence-based clinical protocols — NOT the Drug column from dataset
# (that was a random trial assignment with 0.018 correlation to Status)
DRUG_RECS = {
    1: {
        'primary'   : 'Ursodeoxycholic acid (UDCA) 13–15 mg/kg/day',
        'secondary' : 'Vitamin E supplementation if NASH-related',
        'monitoring': 'LFTs every 6 months · FibroScan annually',
        'goal'      : 'Slow fibrosis progression, maintain liver function',
        'note'      : 'Early stage — good prognosis with consistent management'
    },
    2: {
        'primary'   : 'Ursodeoxycholic acid (UDCA) 13–15 mg/kg/day',
        'secondary' : 'Spironolactone 100mg/day if ascites present · Beta-blockers for portal HTN',
        'monitoring': 'LFTs + ultrasound every 6 months · Endoscopy for varices',
        'goal'      : 'Manage portal hypertension, prevent decompensation',
        'note'      : 'Moderate stage — monitor closely for complications'
    },
    3: {
        'primary'   : 'Spironolactone 100–400mg + Furosemide 40–160mg daily',
        'secondary' : 'Propranolol/Carvedilol for variceal bleeding prevention · Lactulose for encephalopathy',
        'monitoring': 'LFTs monthly · Renal function · Hepatic encephalopathy screening',
        'goal'      : 'Prevent and manage decompensation complications',
        'note'      : 'Advanced stage — aggressive complication management required'
    },
    4: {
        'primary'   : 'Liver transplant evaluation — refer to transplant centre immediately',
        'secondary' : 'Rifaximin 550mg twice daily for encephalopathy · Albumin infusion for SBP',
        'monitoring': 'MELD score calculation weekly · Immediate specialist review',
        'goal'      : 'Transplant listing or palliative care planning',
        'note'      : 'End-stage — urgent specialist referral required'
    }
}


def preprocess_input(form_data: dict) -> pd.DataFrame:
    """
    Convert raw form input from the lab technician into a
    scaled DataFrame ready for model.predict().

    Applies the same transformations as Notebook 02:
      - Hepatomegaly and Spiders are already 0/1 from the form
      - Stage is already int 1-4 from the form
      - All values placed in exact feature order
      - Scaled using the fitted StandardScaler

    Parameters
    ----------
    form_data : dict
        Raw values from the Flask form. Keys must match SELECTED_FEATURES.

    Returns
    -------
    np.ndarray — scaled input ready for model.predict()
    """
    # Build DataFrame in exact feature order the model expects
    input_df = pd.DataFrame([{
        'Bilirubin'   : float(form_data['bilirubin']),
        'Prothrombin' : float(form_data['prothrombin']),
        'Copper'      : float(form_data['copper']),
        'Hepatomegaly': int(form_data['hepatomegaly']),
        'Stage'       : int(form_data['stage']),
        'SGOT'        : float(form_data['sgot']),
        'Spiders'     : int(form_data['spiders']),
    }])[SELECTED_FEATURES]   # enforce column order

    # Scale using the fitted scaler — transform only, never re-fit
    return scaler.transform(input_df)


def predict_patient(form_data: dict) -> dict:
    """
    Full prediction pipeline for a single patient.

    Parameters
    ----------
    form_data : dict
        Raw form values from the lab technician input form.

    Returns
    -------
    dict with:
        predicted_status  — 'C', 'CL', or 'D'
        predicted_outcome — full label string
        confidence        — float 0–1, highest class probability
        prob_alive        — P(C)
        prob_transplant   — P(CL)
        prob_deceased     — P(D)
        confidence_flag   — 'OK' or 'REVIEW'
        primary_drug      — primary treatment recommendation
        secondary_drug    — secondary treatment recommendation
        monitoring        — monitoring protocol
        treatment_goal    — clinical goal
        clinical_note     — stage-specific clinical note
    """
    # 1. Preprocess
    input_scaled = preprocess_input(form_data)

    # 2. Predict
    pred_class  = model.predict(input_scaled)[0]
    pred_proba  = model.predict_proba(input_scaled)[0]

    # 3. Map to labels
    predicted_status  = CLASS_MAP[pred_class]
    predicted_outcome = OUTCOME_MAP[predicted_status]
    confidence        = float(pred_proba.max())

    # 4. Drug recommendation from ENTERED Stage (not predicted status)
    stage = int(form_data['stage'])
    rec   = DRUG_RECS.get(stage, DRUG_RECS[4])

    return {
        'predicted_status' : predicted_status,
        'predicted_outcome': predicted_outcome,
        'confidence'       : round(confidence, 4),
        'prob_alive'       : round(float(pred_proba[0]), 4),
        'prob_transplant'  : round(float(pred_proba[1]), 4),
        'prob_deceased'    : round(float(pred_proba[2]), 4),
        'confidence_flag'  : 'REVIEW' if confidence < 0.60 else 'OK',
        'primary_drug'     : rec['primary'],
        'secondary_drug'   : rec['secondary'],
        'monitoring'       : rec['monitoring'],
        'treatment_goal'   : rec['goal'],
        'clinical_note'    : rec['note'],
    }
