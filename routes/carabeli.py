import os
import requests
from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify, send_from_directory
from datetime import datetime
from werkzeug.utils import secure_filename
from database import get_db_connection
from utils import get_target_folder
from config import SAFE_UPLOADS_FOLDER, WHATSAPP_API_URL, WHATSAPP_API_KEY

carabeli_bp = Blueprint('carabeli', __name__)

@carabeli_bp.route('/cliente/carabeli')
def carabeli_dashboard():
    return render_template('clientes/carabeli_dashboard.html', user_name=session.get('nome','Doutora')) if session.get('empresa')=='carabeli' else redirect(url_for('auth.login'))

@carabeli_bp.route('/api/clinica/whatsapp/config', methods=['GET','POST'])
def api_wa_cfg():
    conn=get_db_connection('carabeli')
    if request.method=='GET': r=conn.execute("SELECT * FROM whatsapp_config").fetchone(); conn.close(); return jsonify(dict(r))
    d=request.json; conn.execute("UPDATE whatsapp_config SET hora_envio=?, status=?",(d['hora_envio'],d['status'])); conn.commit(); conn.close(); return jsonify({'success':True})

@carabeli_bp.route('/api/clinica/whatsapp/connect')
def api_wa_conn():
    try:
        h={"apikey":WHATSAPP_API_KEY,"Content-Type":"application/json"}
        r=requests.post(f"{WHATSAPP_API_URL}/instance/create",json={"instanceName":"clinica_carabelli","qrcode":True},headers=h).json()
        if "already exists" in str(r): r=requests.get(f"{WHATSAPP_API_URL}/instance/connect/clinica_carabelli",headers=h).json()
        if r.get('instance',{}).get('state')=='open': return jsonify({'status':'connected'})
        qr = r.get('qrcode',{}).get('base64') or r.get('base64')
        if qr: return jsonify({'status':'qrcode','qrcode':qr.replace("data:image/png;base64,","").strip()})
        return jsonify({'status':'unknown'})
    except: return jsonify({'error':'erro'})

@carabeli_bp.route('/api/clinica/whatsapp/logout', methods=['DELETE'])
def api_wa_logout(): requests.delete(f"{WHATSAPP_API_URL}/instance/logout/clinica_carabelli",headers={"apikey":WHATSAPP_API_KEY}); return jsonify({'success':True})

@carabeli_bp.route('/api/clinica/pacientes')
def api_pacientes():
    t=request.args.get('q','').lower(); conn=get_db_connection('carabeli')
    sql="SELECT * FROM pacientes WHERE lower(nome) LIKE ? OR cpf LIKE ?" if t else "SELECT * FROM pacientes ORDER BY nome LIMIT 100"
    p=conn.execute(sql,(f'%{t}%',f'%{t}%') if t else ()).fetchall(); conn.close()
    return jsonify([{'id':str(x['id']),'nome':x['nome'],'cpf':x['cpf'],'plano':x['plano'],'telefone':x['telefone']} for x in p])

@carabeli_bp.route('/api/clinica/paciente/novo', methods=['POST'])
def api_pac_novo():
    d=request.json; conn=get_db_connection('carabeli')
    conn.execute("INSERT INTO pacientes (nome, cpf, plano, telefone, email, nascimento, cep, endereco, anamnese) VALUES (?,?,?,?,?,?,?,?,?)",(d['nome'],d['cpf'],d['plano'],d['telefone'],d.get('email'),d['nascimento'],d['cep'],d['endereco'],d['anamnese'])); conn.commit(); conn.close(); return jsonify({'success':True})

@carabeli_bp.route('/api/clinica/paciente/<id>', methods=['GET','PUT','DELETE'])
def api_pac_id(id):
    conn=get_db_connection('carabeli')
    if request.method=='GET': r=conn.execute("SELECT * FROM pacientes WHERE id=?",(id,)).fetchone(); conn.close(); return jsonify(dict(r) if r else {})
    if request.method=='DELETE': conn.execute("DELETE FROM pacientes WHERE id=?",(id,)); conn.commit(); conn.close(); return jsonify({'success':True})
    d=request.json; conn.execute("UPDATE pacientes SET nome=?, cpf=?, plano=?, telefone=?, nascimento=?, cep=?, endereco=?, anamnese=? WHERE id=?",(d['nome'],d['cpf'],d['plano'],d['telefone'],d['nascimento'],d['cep'],d['endereco'],d['anamnese'],id)); conn.commit(); conn.close(); return jsonify({'success':True})

@carabeli_bp.route('/api/clinica/agenda', methods=['GET','POST','PUT','DELETE'])
def api_agenda():
    conn=get_db_connection('carabeli')
    if request.method=='GET': evs=conn.execute("SELECT * FROM agenda").fetchall(); conn.close(); return jsonify([{'id':e['id'],'paciente_id':e['paciente_id'],'title':f"{e['paciente_nome']} - {e['procedimento']}",'start':e['start_time'],'end':e['end_time'],'status':e['status'],'color':'#4ade80' if e['status']=='Confirmado' else ('#94a3b8' if e['status']=='Concluído' else '#38bdf8')} for e in evs])
    d=request.json
    if request.method=='POST': conn.execute("INSERT INTO agenda (paciente_id, paciente_nome, start_time, end_time, procedimento) VALUES (?,?,?,?,?)",(d['paciente_id'],d['paciente_nome'],d['start'],d['end'],d['procedimento'])); conn.commit()
    if request.method=='PUT': conn.execute("UPDATE agenda SET status=? WHERE id=?",(d.get('status'),d.get('id'))); conn.commit()
    if request.method=='DELETE': conn.execute("DELETE FROM agenda WHERE id=?",(request.args.get('id'),)); conn.commit()
    conn.close(); return jsonify({'success':True})

@carabeli_bp.route('/api/clinica/financeiro/<pid>', methods=['GET','POST'])
def api_fin(pid):
    conn=get_db_connection('carabeli')
    if request.method=='POST': d=request.json; conn.execute("INSERT INTO financeiro (paciente_id, data, servico, valor) VALUES (?,?,?,?)",(pid,d['data'],d['servico'],d['valor'])); conn.commit()
    hist=conn.execute("SELECT * FROM financeiro WHERE paciente_id=? ORDER BY id DESC",(pid,)).fetchall()
    pac=conn.execute("SELECT nome FROM pacientes WHERE id=?",(pid,)).fetchone()
    conn.close(); return jsonify({'paciente':dict(pac) if pac else {},'historico':[dict(x) for x in hist]})

@carabeli_bp.route('/api/clinica/faturamento_hoje')
def api_fat_hoje():
    conn=get_db_connection('carabeli'); val=conn.execute("SELECT SUM(valor) FROM financeiro WHERE data=?",(datetime.now().strftime('%Y-%m-%d'),)).fetchone()[0]
    conn.close(); return jsonify({'total':val or 0.0})

@carabeli_bp.route('/api/clinica/relatorios')
def api_rel():
    conn=get_db_connection('carabeli')
    fin=conn.execute("SELECT f.*, p.nome as paciente_nome FROM financeiro f LEFT JOIN pacientes p ON f.paciente_id=p.id ORDER BY f.data DESC").fetchall()
    agd=conn.execute("SELECT * FROM agenda WHERE status='Concluído'").fetchall()
    conn.close(); return jsonify({'financeiro':[dict(x) for x in fin],'agenda':[dict(x) for x in agd]})

@carabeli_bp.route('/api/clinica/estoque', methods=['GET','POST','DELETE'])
def api_est():
    conn=get_db_connection('carabeli')
    if request.method=='GET': i=conn.execute("SELECT * FROM estoque ORDER BY item").fetchall(); conn.close(); return jsonify([dict(x) for x in i])
    if request.method=='DELETE': conn.execute("DELETE FROM estoque WHERE id=?",(request.args.get('id'),)); conn.commit()
    if request.method=='POST': d=request.json; conn.execute("INSERT INTO estoque (item, qtd, unidade, validade) VALUES (?,?,?,?)",(d['item'],d['qtd'],d['unidade'],d['validade'])); conn.commit()
    conn.close(); return jsonify({'success':True})

@carabeli_bp.route('/api/anexos/<target_id>', methods=['GET','POST','DELETE'])
def api_anexos(target_id):
    if 'user_id' not in session: return jsonify({'error':'401'}), 401
    emp=session.get('empresa','carabeli'); full_path,_=get_target_folder(emp, target_id)
    if request.method=='POST': f=request.files['file']; f.save(os.path.join(full_path, secure_filename(f.filename))); return jsonify({'success':True})
    if request.method=='DELETE': os.remove(os.path.join(full_path, request.json['filename'])); return jsonify({'success':True})
    return jsonify({'items':[{'name':f,'url':f"/arquivo_seguro/{emp}/{os.path.basename(full_path)}/{f}",'is_dir':False,'can_delete':True} for f in os.listdir(full_path) if f!='_metadata.json']})

@carabeli_bp.route('/arquivo_seguro/<company>/<folder>/<filename>')
def serve_file(company, folder, filename): return send_from_directory(os.path.join(SAFE_UPLOADS_FOLDER, company, folder), filename)

@carabeli_bp.route('/preencher_ficha/<int:pid>', methods=['GET','POST'])
def public_ficha(pid):
    conn=get_db_connection('carabeli')
    if request.method=='POST': conn.execute("UPDATE pacientes SET anamnese=? WHERE id=?",(request.form.get('anamnese_completa'),pid)); conn.commit(); conn.close(); return render_template('anamnese_paciente.html', sucesso=True)
    p=conn.execute("SELECT nome FROM pacientes WHERE id=?",(pid,)).fetchone(); conn.close()
    return render_template('anamnese_paciente.html', paciente_id=pid, nome_paciente=p['nome'] if p else 'Paciente')
