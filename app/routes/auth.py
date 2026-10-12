# =============================================================
# app/routes/auth.py — Login / Logout
# =============================================================
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app.models import User

auth = Blueprint('auth', __name__)


@auth.route('/')
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user.role)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user     = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password) and user.is_active:
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return _redirect_by_role(user.role)

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


def _redirect_by_role(role):
    routes = {'admin': 'admin.admin_dashboard', 'lab': 'lab.lab_dashboard', 'medic': 'medic.medic_dashboard'}
    return redirect(url_for(routes.get(role, 'auth.login')))
