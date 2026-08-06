import json
import os
from datetime import datetime
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class Storage:
    #default json Storage
    
    def __init__(self, data_path: str = 'data/casino_data.json'):
        self.data_path = data_path
        self.data = self._load_data()
    
    def _load_data(self) -> Dict:
        if os.path.exists(self.data_path):
            try:
                with open(self.data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._default_data()
        return self._default_data()
    
    def _default_data(self) -> Dict:
        return {
            'users': {},  # user_id: {balance, username, first_name, games_played, total_won, total_lost,banned}
            'promo_codes': {},  # code: {amount, used_by, created_at}
            'game_states': {},  # user_id: {game_type: state_data}
            'treasury': 0  # казна чата
        }
    
    def _save(self):
        os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
        with open(self.data_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        return self.data['users'].get(str(user_id))
    
    def create_user(self, user_id: int, username: str = None, first_name: str = None):
        user_id_str = str(user_id)
        if user_id_str not in self.data['users']:
            self.data['users'][user_id_str] = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'balance': 100000,  # Бонус 100к
                'games_played': 0,
                'total_won': 0,
                'total_lost': 0,
                'created_at': datetime.now().isoformat(),
                'banned':False
            }
            self._save()
    
    def get_balance(self, user_id: int) -> int:
        user = self.get_user(user_id)
        return user['balance'] if user else 0
    
    def update_balance(self, user_id: int, amount: int, 
                      transaction_type: str = None, 
                      game_type: str = None, 
                      description: str = None) -> bool:
        user_id_str = str(user_id)
        if user_id_str not in self.data['users']:
            return False
        
        user = self.data['users'][user_id_str]
        user['balance'] += amount
        
        if amount > 0 and transaction_type == 'win':
            user['total_won'] += amount
        elif amount < 0 and transaction_type == 'loss':
            user['total_lost'] += abs(amount)
        
        if game_type:
            user['games_played'] += 1
        
        if 'transactions' not in user:
            user['transactions'] = []
        user['transactions'].append({
            'amount': amount,
            'type': transaction_type,
            'game_type': game_type,
            'description': description,
            'timestamp': datetime.now().isoformat()
        })
        if len(user['transactions']) > 50:
            user['transactions'] = user['transactions'][-50:]
        
        self._save()
        return True
    
    def create_promo_code(self, code: str, amount: int):
        """Создать промокод"""
        self.data['promo_codes'][code.upper()] = {
            'amount': amount,
            'used_by': None,
            'created_at': datetime.now().isoformat()
        }
        self._save()
    
    def use_promo_code(self, code: str, user_id: int) -> Optional[int]:
        code = code.upper()
        promo = self.data['promo_codes'].get(code)
        
        if promo and promo['used_by'] is None:
            promo['used_by'] = str(user_id)
            self._save()
            return promo['amount']
        return None
    
    def save_game_state(self, user_id: int, game_type: str, state_data: Dict):
        user_id_str = str(user_id)
        if user_id_str not in self.data['game_states']:
            self.data['game_states'][user_id_str] = {}
        self.data['game_states'][user_id_str][game_type] = state_data
        self._save()
    
    def get_game_state(self, user_id: int, game_type: str) -> Optional[Dict]:
        user_id_str = str(user_id)
        return self.data['game_states'].get(user_id_str, {}).get(game_type)
    
    def clear_game_state(self, user_id: int, game_type: str):
        user_id_str = str(user_id)
        if user_id_str in self.data['game_states']:
            self.data['game_states'][user_id_str].pop(game_type, None)
            self._save()
    
    def get_top_players(self, limit: int = 10) -> List[Dict]:
        users = self.data['users'].values()
        sorted_users = sorted(users, key=lambda x: x['balance'], reverse=True)
        return list(sorted_users)[:limit]
    
    def get_all_users(self) -> List[Dict]:
        return list(self.data['users'].values())
    
    def get_treasury(self) -> int:
        return self.data.get('treasury', 0)
    
    def add_to_treasury(self, amount: int):
        self.data['treasury'] = self.data.get('treasury', 0) + amount
        self._save()

    def ban_user(self,user_id:int)->bool:
        user_id_str=str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['banned']=True
            self._save()
            return True
        return False

    def unban_user(self,user_id:int)->bool:
        user_id_str=str(user_id)
        if user_id_str in self.data['users']:
            self.data['users'][user_id_str]['banned']=False
            self._save()
            return True
        return False

    def is_banned(self,user_id:int)->bool:
        user=self.get_user(user_id)
        return user.get('banned',False) if user else False

    def get_banned_users(self)->List[Dict]:
        return [user for user in self.data['users'].values() if user.get('banned',False)]
    def _is_promo_exists(self, code: str) -> bool:
        """Проверить существует ли промокод"""
        code = code.upper()
        return code in self.data['promo_codes']
