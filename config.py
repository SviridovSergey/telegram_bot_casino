import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Безопасное получение ADMIN_IDS
    ADMIN_IDS = []
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    if admin_ids_str:
        for id_str in admin_ids_str.split(','):
            id_str = id_str.strip()
            if id_str and id_str.isdigit():
                ADMIN_IDS.append(int(id_str))
    
    # Путь к данным
    DATA_PATH = 'data/casino_data.json'
