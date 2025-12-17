from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from werkzeug.security import check_password_hash
from database import get_db_connection

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email'); senha=request.form.get('senha')
        conn=get_db_connection('main'); user=conn.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); conn.close()
        if user and check_password_hash(user['senha'], senha):
            session['user_id']=user['id']; session['nome']=user['nome']; session['empresa']=user['empresa']
            return redirect(url_for('admin.admin_dashboard') if user['empresa']=='admin' else f"/cliente/{user['empresa']}")
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout(): session.clear(); return redirect('/')
