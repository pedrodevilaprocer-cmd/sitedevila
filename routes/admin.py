from flask import Blueprint, render_template, request, redirect, session, flash, url_for
from database import get_db_connection

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('empresa') != 'admin': return redirect(url_for('auth.login'))
    conn = get_db_connection('main')
    if request.method == 'POST':
        conn.execute('UPDATE users SET empresa=?, cargo=? WHERE id=?', (request.form.get('nova_empresa'), request.form.get('novo_cargo'), request.form.get('user_id'))); conn.commit()
        flash("Atualizado.")
    users = conn.execute('SELECT * FROM users').fetchall(); conn.close()
    return render_template('admin/admin.html', users=users)

@admin_bp.route('/admin/excluir', methods=['POST'])
def excluir():
    conn = get_db_connection('main'); conn.execute('DELETE FROM users WHERE id=?', (request.form.get('user_id'),)); conn.commit(); conn.close()
    return redirect(url_for('admin.admin_dashboard'))
