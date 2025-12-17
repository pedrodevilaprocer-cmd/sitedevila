from datetime import datetime
from flask import Blueprint, request, jsonify
from database import get_db_connection

n8n_bp = Blueprint('n8n', __name__)

@n8n_bp.route('/api/n8n/consultar_agenda', methods=['GET'])
def n8n_consultar_agenda():
    """
    Uso no n8n: GET http://host.docker.internal:8000/api/n8n/consultar_agenda?data=2025-12-16
    Se não enviar data, pega a de hoje.
    """
    data_alvo = request.args.get('data', datetime.now().strftime('%Y-%m-%d'))

    try:
        conn = get_db_connection('carabeli')
        # Busca agendamentos que começam com a data YYYY-MM-DD
        agendamentos = conn.execute(
            "SELECT start_time, paciente_nome, procedimento, status, obs FROM agenda WHERE start_time LIKE ? ORDER BY start_time ASC",
            (f"{data_alvo}%",)
        ).fetchall()
        conn.close()

        if not agendamentos:
            return jsonify({"mensagem": f"Nenhum agendamento encontrado para {data_alvo}.", "total": 0})

        # Formata para a IA entender fácil
        lista_limpa = []
        for ag in agendamentos:
            hora = ag['start_time'].split('T')[1][:5] # Pega só HH:MM
            lista_limpa.append({
                "horario": hora,
                "paciente": ag['paciente_nome'],
                "procedimento": ag['procedimento'],
                "status": ag['status'],
                "obs": ag['obs'] or ""
            })

        return jsonify({"data": data_alvo, "agendamentos": lista_limpa, "total": len(lista_limpa)})

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@n8n_bp.route('/api/n8n/buscar_paciente', methods=['GET'])
def n8n_buscar_paciente():
    """
    Uso no n8n: GET http://host.docker.internal:8000/api/n8n/buscar_paciente?nome=Joao
    """
    termo = request.args.get('nome', '').lower()
    if not termo:
        return jsonify({"erro": "Forneça um nome para busca."})

    try:
        conn = get_db_connection('carabeli')
        pacientes = conn.execute(
            "SELECT id, nome, telefone, plano, anamnese FROM pacientes WHERE lower(nome) LIKE ? LIMIT 5",
            (f"%{termo}%",)
        ).fetchall()
        conn.close()

        resultado = [dict(p) for p in pacientes]
        return jsonify(resultado)

    except Exception as e:
        return jsonify({"erro": str(e)}), 500
