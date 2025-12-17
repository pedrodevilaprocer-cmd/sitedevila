import os
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from datetime import datetime
import requests
from config import API_TOKEN, API_URL_BUSCA, UPLOAD_BASE_FOLDER
from utils import limpar_nome
from database import get_db_connection

procer_bp = Blueprint('procer', __name__)

@procer_bp.route('/cliente/procer')
def procer_dashboard():
    return render_template('clientes/procer_dashboard.html') if session.get('empresa')=='procer' else redirect(url_for('auth.login'))

@procer_bp.route('/cliente/procer/testes')
def procer_testes_dashboard():
    return render_template('clientes/dashboard_testes.html', user_name=session['nome']) if session.get('empresa')=='procer' else redirect(url_for('auth.login'))

@procer_bp.route('/cliente/procer/testes/lista')
def procer_testes_lista():
    return render_template('clientes/procer_testes.html', ops=[]) if session.get('empresa')=='procer' else redirect(url_for('auth.login'))

@procer_bp.route('/api/projetos-quadros')
def api_projetos_quadros():
    termo = request.args.get('q', '')
    try:
        h = {'Content-Type': 'application/json', 'Authorization': API_TOKEN}
        r = requests.get(API_URL_BUSCA, headers=h, params={"filter": termo}, timeout=10)
        return jsonify(r.json()[:100] if r.status_code == 200 else [])
    except: return jsonify([])

@procer_bp.route('/api/active_projects', methods=['GET', 'POST', 'DELETE'])
def manage_active_projects():
    conn = get_db_connection('main')
    if request.method == 'GET': r = conn.execute('SELECT * FROM active_projects ORDER BY added_at DESC').fetchall(); conn.close(); return jsonify([dict(x) for x in r])
    if request.method == 'POST': d = request.json; conn.execute('INSERT OR IGNORE INTO active_projects (id, descricao, added_by, added_at) VALUES (?, ?, ?, ?)', (d['id'], d['descricao'], session['nome'], datetime.now())); conn.commit(); conn.close(); return jsonify({'success': True})
    if request.method == 'DELETE': conn.execute('DELETE FROM active_projects WHERE id = ?', (request.args.get('id'),)); conn.commit(); conn.close(); return jsonify({'success': True})

@procer_bp.route('/upload_evidencias', methods=['POST'])
def upload_evidencias():
    try:
        path = os.path.join(UPLOAD_BASE_FOLDER, limpar_nome(request.form.get('item_desc')), limpar_nome(f"OV_{request.form.get('ov_numero')}"))
        if not os.path.exists(path): os.makedirs(path)
        for i in range(4):
            if f'foto_{i}' in request.files: f = request.files[f'foto_{i}']; f.save(os.path.join(path, f"OP_{request.form.get('op_numero')}_{i}.jpg"))
        return jsonify({'success': True})
    except Exception as e: return jsonify({'success': False, 'message': str(e)}), 500
