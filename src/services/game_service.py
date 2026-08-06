import random
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class GameService:
    def __init__(self, storage):
        self.storage = storage
    
    def coinflip(self, user_id: int, amount: int, choice: str) -> Dict:
        """Орел/Решка"""
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            return {'success': False, 'message': 'Недостаточно средств!'}
        
        result = random.choice(['орел', 'решка'])
        win = (choice.lower() == result)
        
        if win:
            win_amount = amount * 2
            self.storage.update_balance(user_id, win_amount, 'win', 'coinflip', f'Выиграл в орёл/решку')
            return {
                'success': True,
                'win': True,
                'amount': win_amount,
                'result': result,
                'message': f'🎉 Выпал {result}! Вы выиграли {win_amount} GRAM!'
            }
        else:
            self.storage.update_balance(user_id, -amount, 'loss', 'coinflip', f'Проиграл в орёл/решку')
            return {
                'success': True,
                'win': False,
                'amount': amount,
                'result': result,
                'message': f'😔 Выпал {result}. Вы проиграли {amount} GRAM'
            }
    
    def mines(self, user_id: int, amount: int) -> Dict:
        """Игра мины"""
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            return {'success': False, 'message': 'Недостаточно средств!'}
        
        # Генерация минного поля (5x5 = 25 клеток, 5 мин)
        mines = random.sample(range(25), 5)
        safe_cells = [i for i in range(25) if i not in mines]
        selected = random.choice(safe_cells)
        
        win_multiplier = 1.5 + (random.random() * 0.5)  # от 1.5 до 2.0
        win_amount = int(amount * win_multiplier)
        
        self.storage.update_balance(user_id, win_amount - amount, 'win', 'mines', f'Выиграл в мины')
        
        return {
            'success': True,
            'win': True,
            'amount': win_amount,
            'win_amount': win_amount - amount,
            'multiplier': round(win_multiplier, 2),
            'message': f'💣 Мины! Вы выиграли {win_amount} GRAM (x{round(win_multiplier, 2)})!'
        }
    
    def joker(self, user_id: int, amount: int) -> Dict:
        """Игра Джокер"""
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            return {'success': False, 'message': 'Недостаточно средств!'}
        
        rand = random.random()
        
        if rand < 0.1:  # Джекпот x5
            win_amount = amount * 5
            self.storage.update_balance(user_id, win_amount, 'win', 'joker', f'ДЖЕКПОТ в Джокере!')
            return {
                'success': True,
                'win': True,
                'amount': win_amount,
                'type': 'jackpot',
                'message': f'🎰 ДЖЕКПОТ! Вы выиграли {win_amount} GRAM (x5)!'
            }
        elif rand < 0.5:  # Обычный выигрыш x2
            win_amount = amount * 2
            self.storage.update_balance(user_id, win_amount, 'win', 'joker', f'Выиграл в Джокере')
            return {
                'success': True,
                'win': True,
                'amount': win_amount,
                'type': 'win',
                'message': f'🎰 Вы выиграли {win_amount} GRAM (x2)!'
            }
        else:  # Проигрыш
            self.storage.update_balance(user_id, -amount, 'loss', 'joker', f'Проиграл в Джокере')
            return {
                'success': True,
                'win': False,
                'amount': amount,
                'type': 'loss',
                'message': f'😔 Вы проиграли {amount} GRAM'
            }
