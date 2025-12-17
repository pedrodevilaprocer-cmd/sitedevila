import re
import os
import json
from config import SAFE_UPLOADS_FOLDER
from database import get_db_connection

def limpar_nome(nome): return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', str(nome)).strip()

def get_target_folder(company, folder_id):
    company_path = os.path.join(SAFE_UPLOADS_FOLDER, company)
    if not os.path.exists(company_path): os.makedirs(company_path)
    prefix_type = "projeto" if company == 'procer' else "paciente"
    base_prefix = f"{prefix_type}_{folder_id}"
    for folder_name in os.listdir(company_path):
        if folder_name.startswith(base_prefix + "_") or folder_name == base_prefix:
            return os.path.join(company_path, folder_name), folder_name
    item_name = "Item"
    try:
        conn = get_db_connection('carabeli' if company=='carabeli' else 'main')
        sql = "SELECT nome FROM pacientes WHERE id=?" if company=='carabeli' else "SELECT descricao FROM active_projects WHERE id=?"
        res = conn.execute(sql, (folder_id,)).fetchone()
        if res: item_name = res[0]
        conn.close()
    except: pass
    new_folder_name = f"{base_prefix}_{limpar_nome(item_name)}"
    full_path = os.path.join(company_path, new_folder_name)
    os.makedirs(full_path, exist_ok=True)
    return full_path, new_folder_name

def get_metadata_path(full_path): return os.path.join(full_path, '_metadata.json')
def load_metadata(full_path):
    path = get_metadata_path(full_path)
    if os.path.exists(path):
        try: return json.load(open(path, 'r'))
        except: return {}
    return {}
def save_metadata(full_path, data):
    with open(get_metadata_path(full_path), 'w') as f: json.dump(data, f)
