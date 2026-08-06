from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import logging
import re
import random

logger = logging.getLogger(__name__)

class GameHandlers:
    def __init__(self, storage, game_service):
        self.storage = storage  # исправлено: storage вместо db
        self.game_service = game_service

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.storage.create_user(user.id, user.username, user.first_name)  # storage
        await update.message.reply_text(
            f"🎰 Привет, {user.first_name}!\n\n"
            f"Я бот-казино для вашего чата!\n"
            f"💰 Твой баланс: {self.storage.get_balance(user.id)} GRAM\n\n"
            f"Используй /help для списка команд"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        help_text = """
🤖 *Команды бота-казино*

🎮 *ИГРЫ:*
• `/balance` - показать баланс
• `/mines [сумма]` - играть в минное поле
• `/joker [сумма]` - играть в джокер
• `/coinflip [сумма]` - подбросить монетку

💸 *ПЕРЕВОДЫ И ПРОМОКОДЫ:*
• `/transfer [сумма]` - перевести средства (ответь на сообщение)
• `#КОД` - активировать промокод

🏆 *ТОП:*
• `/top` - топ игроков в чате

💰 Твой баланс: {} GRAM
        """.format(self.storage.get_balance(update.effective_user.id))
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        user = update.effective_user
        balance = self.storage.get_balance(user.id)
        await update.message.reply_text(f"Твой баланс: {balance} GRAM")

    async def _check_banned(self, update: Update) -> bool:
        user_id = update.effective_user.id
        if self.storage.is_banned(user_id):
            await update.message.reply_text(
                "🚫 Вы забанены в этом боте!\n"
                "❌ Вы не можете использовать команды.\n"
                "Для снятия бана обратитесь к администратору."
            )
            return True
        return False

    async def transfer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        if not context.args:
            await update.message.reply_text("❌ Использование: `/transfer [сумма]` (ответь на сообщение пользователя)")
            return
        try:
            amount = int(context.args[0])
            if amount <= 0:
                await update.message.reply_text("❌ Сумма должна быть положительной")
                return
        except ValueError:
            await update.message.reply_text("❌ Введи корректную сумму")
            return

        sender_id = update.effective_user.id
        sender_balance = self.storage.get_balance(sender_id)
        if sender_balance < amount:
            await update.message.reply_text(f"❌ Недостаточно средств! Твой баланс: {sender_balance} GRAM")
            return
        
        recipient_id = None
        if update.message.reply_to_message:
            recipient_id = update.message.reply_to_message.from_user.id

        if not recipient_id:
            await update.message.reply_text("❌ Ответь на сообщение пользователя, которому хочешь перевести GRAM")
            return
        
        if recipient_id == sender_id:
            await update.message.reply_text("❌ Нельзя перевести самому себе!")
            return
        
        self.storage.update_balance(sender_id, -amount, 'transfer_out', None, f'Перевод пользователю {recipient_id}')
        self.storage.update_balance(recipient_id, amount, 'transfer_in', None, f'Получен перевод от {sender_id}')
        
        await update.message.reply_text(f"✅ Переведено {amount} GRAM пользователю!")

    async def mines_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        if not context.args:
            await update.message.reply_text("❌ Использование: `/mines [сумма]`")
            return
    
        try:
            amount = int(context.args[0])
            if amount <= 0:
                await update.message.reply_text("❌ Сумма должна быть положительной")
                return
        except ValueError:
            await update.message.reply_text("❌ Введи корректную сумму")
            return
    
        user_id = update.effective_user.id
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            await update.message.reply_text(f"❌ Недостаточно средств! Твой баланс: {balance} GRAM")
            return
    
        # Генерируем поле 5x5
        field = []
        mines_positions = random.sample(range(25), 5)
    
        for i in range(25):
            if i in mines_positions:
                field.append('💣')
            else:
                multipliers = [1.5, 2.0, 2.5, 3.0, 5.0, 10.0, 25.0]
                field.append(f'×{random.choice(multipliers)}')
    
        random.shuffle(field)
    
        # Создаем кнопки для поля
        keyboard = []
        row = []
        for i in range(25):
            button = InlineKeyboardButton("❓", callback_data=f"mines_{i}_{amount}")
            row.append(button)
            if len(row) == 5:
                keyboard.append(row)
                row = []
    
        keyboard.append([InlineKeyboardButton("💰 Забрать выигрыш", callback_data=f"mines_take_{amount}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
    
        # Сохраняем состояние игры
        context.user_data['mines_game'] = {
            'amount': amount,
            'field': field,
            'revealed': [],
            'message_id': None,  # будем хранить ID сообщения
            'chat_id': update.effective_chat.id
        }
    
        msg = await update.message.reply_text(
            f"💣 *Минное поле*\n\n"
            f"💰 Ставка: *{amount} GRAM*\n"
            f"🎯 Найди 3 безопасные клетки!\n\n"
            f"*Поле 5×5:*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
        # Сохраняем ID сообщения для обновления
        context.user_data['mines_game']['message_id'] = msg.message_id
    async def joker_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        if not context.args:
            await update.message.reply_text("❌ Использование: `/joker [сумма]`")
            return
        try:
            amount = int(context.args[0])
            if amount <= 0:
                await update.message.reply_text("❌ Сумма должна быть положительной")
                return
        except ValueError:
            await update.message.reply_text("❌ Введи корректную сумму")
            return
        
        user_id = update.effective_user.id
        result = self.game_service.joker(user_id, amount)

        if not result['success']:
            await update.message.reply_text(f"❌ {result['message']}")
            return
        
        await update.message.reply_text(
            f"{result['message']}\n"
            f"Твой новый баланс: {self.storage.get_balance(user_id)} GRAM"
        )

    
    async def mines_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
    
        data = query.data.split('_')
        user_id = update.effective_user.id
    
        if self.storage.is_banned(user_id):
            await query.edit_message_text("🚫 Вы забанены!")
            return
    
        if len(data) < 3 or data[0] != 'mines':
            await query.edit_message_text("❌ Ошибка в данных")
            return
    
        cell_index = int(data[1])
        amount = int(data[2])
    
        game_state = context.user_data.get('mines_game', {})
        field = game_state.get('field', [])
        message_id = game_state.get('message_id')
        chat_id = game_state.get('chat_id')
    
        if not field:
            await query.edit_message_text("❌ Игра не найдена. Начни заново.")
            return
    
        if len(field) != 25:
            await query.edit_message_text("❌ Ошибка поля. Начни заново.")
            return
    
        if cell_index not in range(25):
            await query.edit_message_text("❌ Неверная клетка")
            return
    
        revealed = game_state.get('revealed', [])
        if cell_index in revealed:
            await query.answer("⚠️ Эта клетка уже открыта!")
            return
    
        revealed.append(cell_index)
        game_state['revealed'] = revealed
    
        cell_value = field[cell_index]
    
        if cell_value == '💣':
            # Попали на мину - проигрыш
            self.storage.update_balance(user_id, -amount, 'loss', 'mines', 'Проиграл в мины')
        
            # Показываем все поле с минами
            display = []
            for i in range(25):
                if field[i] == '💣':
                    display.append('💣')
                elif i in revealed:
                    display.append(field[i])
                else:
                    display.append('❓')
        
            text = f"💥 *БАХ! Ты наступил на мину!*\n\n"
            for i in range(0, 25, 5):
                text += ' '.join(display[i:i+5]) + '\n'
            text += f"\n💸 Проигрыш: *{amount} GRAM*\n"
            text += f"💰 Новый баланс: *{self.storage.get_balance(user_id)} GRAM*"
        
            # Редактируем сообщение, убираем кнопки
            await query.edit_message_text(text, parse_mode='Markdown')
            context.user_data.pop('mines_game', None)
            return
    
        # Безопасная клетка
        multiplier = float(cell_value.replace('×', ''))
        win_amount = int(amount * multiplier)
        revealed_count = len(revealed)
    
        # Проверяем - открыто 3 клетки или больше
        if revealed_count >= 3:
            # Автоматический выигрыш
            self.storage.update_balance(user_id, win_amount, 'win', 'mines', f'Выиграл в мины: ×{multiplier}')
        
            display = []
            for i in range(25):
                if i in revealed:
                    display.append(field[i])
                elif field[i] == '💣':
                    display.append('❓')
                else:
                    display.append('❓')
        
            text = f"🎉 *Поздравляю! Ты выиграл!*\n\n"
            for i in range(0, 25, 5):
                text += ' '.join(display[i:i+5]) + '\n'
            text += f"\n💰 Выигрыш: *{win_amount} GRAM* (×{multiplier})\n"
            text += f"📈 Чистая прибыль: *{win_amount - amount} GRAM*\n"
            text += f"💳 Новый баланс: *{self.storage.get_balance(user_id)} GRAM*"
        
            await query.edit_message_text(text, parse_mode='Markdown')
            context.user_data.pop('mines_game', None)
            return
    
        # Продолжаем игру - обновляем поле на месте
        display = []
        for i in range(25):
            if i in revealed:
                display.append(field[i])
            else:
                display.append('❓')
    
        # Создаем обновленное поле с кнопками
        keyboard = []
        row = []
        for i in range(25):
            if i in revealed:
                button = InlineKeyboardButton(field[i], callback_data="empty")
            else:
                button = InlineKeyboardButton("❓", callback_data=f"mines_{i}_{amount}")
            row.append(button)
            if len(row) == 5:
                keyboard.append(row)
                row = []
    
        keyboard.append([InlineKeyboardButton("💰 Забрать выигрыш", callback_data=f"mines_take_{amount}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
    
        text = f"💣 *Минное поле*\n\n"
        text += f"💰 Ставка: *{amount} GRAM*\n"
        text += f"🎯 Открыто клеток: *{revealed_count}/3*\n"
        text += f"📈 Множитель: *×{multiplier}*\n"
        text += f"💵 Потенциальный выигрыш: *{win_amount} GRAM*\n\n"
    
        for i in range(0, 25, 5):
            text += ' '.join(display[i:i+5]) + '\n'
    
        # Редактируем существующее сообщение
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
        context.user_data['mines_game'] = game_state

    async def mines_take_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
    
        data = query.data.split('_')
        user_id = update.effective_user.id
    
        if self.storage.is_banned(user_id):
            await query.edit_message_text("🚫 Вы забанены!")
            return
    
        if len(data) < 2:
            await query.edit_message_text("❌ Ошибка в данных")
            return
    
        amount = int(data[1])
    
        game_state = context.user_data.get('mines_game', {})
        field = game_state.get('field', [])
        revealed = game_state.get('revealed', [])
    
        if not field or not revealed:
            await query.edit_message_text("❌ Игра не найдена. Начни заново.")
            return
    
        # Расчет выигрыша
        last_revealed = revealed[-1]
        last_value = field[last_revealed]
    
        if last_value == '💣':
            await query.edit_message_text("❌ Нельзя забрать выигрыш на мине!")
            return
    
        multiplier = float(last_value.replace('×', ''))
        win_amount = int(amount * multiplier)
    
        self.storage.update_balance(user_id, win_amount, 'win', 'mines', f'Забрал выигрыш: ×{multiplier}')
    
        display = []
        for i in range(25):
            if i in revealed:
                display.append(field[i])
            elif field[i] == '💣':
                display.append('❓')
            else:
                display.append('❓')
    
        text = f"🎉 *Ты забрал выигрыш!*\n\n"
        for i in range(0, 25, 5):
            text += ' '.join(display[i:i+5]) + '\n'
        text += f"\n💰 Выигрыш: *{win_amount} GRAM* (×{multiplier})\n"
        text += f"📈 Чистая прибыль: *{win_amount - amount} GRAM*\n"
        text += f"💳 Новый баланс: *{self.storage.get_balance(user_id)} GRAM*"
    
        await query.edit_message_text(text, parse_mode='Markdown')
        context.user_data.pop('mines_game', None)
    
    async def coinflip_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        if not context.args:
            await update.message.reply_text("❌ Использование: `/coinflip [сумма]`")
            return
        
        try:
            amount = int(context.args[0])
            if amount <= 0:
                await update.message.reply_text("❌ Сумма должна быть положительной")
                return
        except ValueError:
            await update.message.reply_text("❌ Введи корректную сумму")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("Орел", callback_data=f"coinflip_орел_{amount}"),
                InlineKeyboardButton("Решка", callback_data=f"coinflip_решка_{amount}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Сделай выбор! Ставка: {amount} GRAM",
            reply_markup=reply_markup
        )
    
    async def coinflip_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data.split('_')
        if len(data) != 3:
            await query.edit_message_text("❌ Ошибка в данных")
            return
        
        choice = data[1]
        amount = int(data[2])
        user_id = update.effective_user.id
        
        result = self.game_service.coinflip(user_id, amount, choice)
        
        await query.edit_message_text(
            f"{result['message']}\n"
            f"Твой новый баланс: {self.storage.get_balance(user_id)} GRAM"
        )
    
    async def top_players(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        top = self.storage.get_top_players(10)
        if not top:
            await update.message.reply_text("Пока нет игроков в топе")
            return
        
        text = "*Топ игроков чата:*\n\n"
        for i, player in enumerate(top, 1):
            name = player.get('first_name') or player.get('username') or f"User{player['user_id']}"
            text += f"{i}. {name} - {player['balance']} GRAM (игр: {player['games_played']})\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def promo_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if await self._check_banned(update):
            return
        if not context.args:
            await update.message.reply_text("❌ Использование: `#КОД`")
            return
        
        code = context.args[0].lstrip('#')
        user_id = update.effective_user.id
        
        amount = self.storage.use_promo_code(code, user_id)
        if amount:
            self.storage.update_balance(user_id, amount, 'promo', None, f'Активирован промокод {code}')
            await update.message.reply_text(f"✅ Промокод активирован! Получено {amount} GRAM!\n💰 Твой баланс: {self.storage.get_balance(user_id)} GRAM")
        else:
            await update.message.reply_text("❌ Недействительный или уже использованный промокод")

    # ===== АДМИН-КОМАНДЫ =====
    async def admin_add_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Использование:\n"
                "/add @username 1000\n"
                "Или ответь на сообщение: /add 1000"
            )
            return
        
        recipient_id = None
        amount = None
        
        if update.message.reply_to_message:
            recipient_id = update.message.reply_to_message.from_user.id
            try:
                amount = int(context.args[0])
            except:
                await update.message.reply_text("❌ Введи корректную сумму")
                return
        else:
            try:
                # Пробуем как @username или ID
                if context.args[0].startswith('@'):
                    # Поиск по username (упрощенно)
                    await update.message.reply_text("❌ Используй ID или ответь на сообщение")
                    return
                else:
                    recipient_id = int(context.args[0])
                    amount = int(context.args[1])
            except:
                await update.message.reply_text("❌ Укажи ID пользователя или ответь на его сообщение")
                return
        
        if not recipient_id:
            await update.message.reply_text("❌ Не удалось определить получателя")
            return
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной")
            return
        
        self.storage.update_balance(recipient_id, amount, 'admin_gift', None, f'Админ выдал {amount} GRAM')
        await update.message.reply_text(
            f"Выдано {amount} GRAM пользователю!\n"
            f"Новый баланс: {self.storage.get_balance(recipient_id)} GRAM"
        )
    
    async def admin_create_promo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Использование: /promo [код] [сумма]\n"
                "Пример: /promo SUMMER2026 50000"
            )
            return
        
        code = context.args[0].upper()
        try:
            amount = int(context.args[1])
        except:
            await update.message.reply_text("❌ Введи корректную сумму")
            return
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной")
            return
        
        self.storage.create_promo_code(code, amount)
        
        await update.message.reply_text(
            f"Промокод создан!\n"
            f"Код: #{code}\n"
            f"Сумма: {amount} GRAM"
        )
    
    async def admin_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if not context.args:
            await update.message.reply_text("❌ Использование: /userbal [ID пользователя]")
            return
        
        try:
            target_id = int(context.args[0])
        except:
            await update.message.reply_text("❌ Укажи ID пользователя")
            return
        
        user_info = self.storage.get_user(target_id)
        if not user_info:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        await update.message.reply_text(
            f"Пользователь: {user_info.get('first_name', 'Unknown')}\n"
            f"ID: {target_id}\n"
            f"Баланс: {user_info['balance']} GRAM\n"
            f"Игр сыграно: {user_info['games_played']}"
        )
    
    async def admin_all_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        users = self.storage.get_all_users()
        if not users:
            await update.message.reply_text("Пока нет пользователей")
            return
        
        sorted_users = sorted(users, key=lambda x: x['balance'], reverse=True)
        text = "*Все пользователи:*\n\n"
        for i, user in enumerate(sorted_users[:20], 1):
            name = user.get('first_name') or user.get('username') or f"User{user['user_id']}"
            text += f"{i}. {name} - {user['balance']} GRAM\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def admin_set_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("❌ Использование: /setbalance [ID] [сумма]")
            return
        
        try:
            target_id = int(context.args[0])
            new_balance = int(context.args[1])
        except:
            await update.message.reply_text("❌ Введи корректные данные")
            return
        
        if new_balance < 0:
            await update.message.reply_text("❌ Баланс не может быть отрицательным")
            return
        
        current_balance = self.storage.get_balance(target_id)
        difference = new_balance - current_balance
        
        if difference != 0:
            self.storage.update_balance(target_id, difference, 'admin_set', None, f'Админ установил баланс {new_balance}')
        
        await update.message.reply_text(f"✅ Баланс обновлен! Новый баланс: {new_balance} GRAM")


    async def admin_take_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Использование: /take [ID пользователя] [сумма]\n"
                "Пример: /take 123456789 50000\n"
                "Или ответь на сообщение: /take 50000"
            )
            return
        
        recipient_id = None
        amount = None
        
        if update.message.reply_to_message:
            recipient_id = update.message.reply_to_message.from_user.id
            try:
                amount = int(context.args[0])
            except:
                await update.message.reply_text("❌ Введи корректную сумму")
                return
        else:
            try:
                recipient_id = int(context.args[0])
                amount = int(context.args[1])
            except:
                await update.message.reply_text("❌ Укажи ID пользователя или ответь на его сообщение")
                return
        
        if not recipient_id:
            await update.message.reply_text("❌ Не удалось определить получателя")
            return
        
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительной")
            return
        
        current_balance = self.storage.get_balance(recipient_id)
        if current_balance < amount:
            await update.message.reply_text(
                f"У пользователя недостаточно средств!\n"
                f"Баланс: {current_balance} GRAM\n"
                f"Запрошено: {amount} GRAM"
            )
            return
        self.storage.update_balance(recipient_id, -amount, 'admin_take', None, f'Админ забрал {amount} GRAM')
        self.storage.add_to_treasury(amount)
        user_info = self.storage.get_user(recipient_id)
        user_name = user_info.get('first_name', 'Пользователь') if user_info else 'Пользователь'
        
        await update.message.reply_text(
            f"Забрано {amount} GRAM у пользователя {user_name}\n"
            f"Новый баланс: {self.storage.get_balance(recipient_id)} GRAM\n"
            f"В казне: {self.storage.get_treasury()} GRAM"
        )
        
        try:
            await context.bot.send_message(
                recipient_id,
                f"Админ забрал у тебя {amount} GRAM!\n"
                f"Твой баланс: {self.storage.get_balance(recipient_id)} GRAM"
            )
        except:
            pass
    
    async def admin_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 1 and not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Использование: /ban [ID пользователя]\n"
                "Или ответь на сообщение пользователя: /ban"
            )
            return
        
        recipient_id = None
        if update.message.reply_to_message:
            recipient_id = update.message.reply_to_message.from_user.id
        else:
            try:
                recipient_id = int(context.args[0])
            except:
                await update.message.reply_text("❌ Укажи ID пользователя")
                return
        
        if not recipient_id:
            await update.message.reply_text("❌ Не удалось определить пользователя")
            return
        
        if recipient_id == user_id:
            await update.message.reply_text("❌ Нельзя забанить самого себя!")
            return
        
        user_info = self.storage.get_user(recipient_id)
        if not user_info:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        if self.storage.ban_user(recipient_id):
            user_name = user_info.get('first_name', 'Пользователь')
            await update.message.reply_text(
                f"Пользователь {user_name} забанен!\n"
                f"ID: {recipient_id}\n"
                f"Он больше не сможет пользоваться ботом"
            )
            
            try:
                await context.bot.send_message(
                    recipient_id,
                    "Вы были забанены в боте-казино!\n"
                    "Вы больше не можете пользоваться ботом.\n"
                    "Для снятия бана обратитесь к администратору."
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка при бане пользователя")
    
    async def admin_unban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 1 and not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Использование: /unban [ID пользователя]\n"
                "Или ответь на сообщение пользователя: /unban"
            )
            return
        
        recipient_id = None
        if update.message.reply_to_message:
            recipient_id = update.message.reply_to_message.from_user.id
        else:
            try:
                recipient_id = int(context.args[0])
            except:
                await update.message.reply_text("❌ Укажи ID пользователя")
                return
        
        if not recipient_id:
            await update.message.reply_text("❌ Не удалось определить пользователя")
            return
        
        user_info = self.storage.get_user(recipient_id)
        if not user_info:
            await update.message.reply_text("❌ Пользователь не найден")
            return
        
        if self.storage.unban_user(recipient_id):
            user_name = user_info.get('first_name', 'Пользователь')
            await update.message.reply_text(
                f"Бан снят с пользователя {user_name}\n"
                f"ID: {recipient_id}\n"
                f"Пользователь снова может пользоваться ботом"
            )
            
            try:
                await context.bot.send_message(
                    recipient_id,
                    "Администратор снял с вас бан!\n"
                    "Вы снова можете пользоваться ботом."
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка при разбане пользователя")
    
    async def admin_banned_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        banned_users = self.storage.get_banned_users()
        if not banned_users:
            await update.message.reply_text("Нет забаненных пользователей")
            return
        
        text = "*Список забаненных пользователей:*\n\n"
        for user in banned_users:
            name = user.get('first_name') or user.get('username') or f"User{user['user_id']}"
            text += f"{name} (ID: {user['user_id']})\n"
            text += f"Баланс: {user['balance']} GRAM\n"
            text += f"Игр: {user['games_played']}\n"
            text += f"Забанен: {user.get('created_at', 'Неизвестно')}\n"
            text += "—" * 30 + "\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def admin_treasury(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        treasury = self.storage.get_treasury()
        await update.message.reply_text(
            f"*Казна чата*\n\n"
            f"Всего в казне: {treasury} GRAM\n\n"
            f"Статистика:\n"
            f"• Пользователей: {len(self.storage.get_all_users())}\n"
            f"• Забаненных: {len(self.storage.get_banned_users())}"
        )
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений (промокоды через #)"""
        if await self._check_banned(update):
            return
    
        text = update.message.text.strip()
    
        # Проверяем если сообщение начинается с #
        if text.startswith('#'):
            code = text[1:].strip()
            user_id = update.effective_user.id
        
            # Проверяем существование промокода
            if not self.storage._is_promo_exists(code):
                await update.message.reply_text("❌ Недействительный промокод!")
                return
        
            amount = self.storage.use_promo_code(code, user_id)
            if amount:
                self.storage.update_balance(user_id, amount, 'promo', None, f'Активирован промокод {code}')
                await update.message.reply_text(
                    f"✅ *Промокод активирован!*\n\n"
                    f"💰 Получено: *{amount} GRAM*\n"
                    f"💳 Твой баланс: *{self.storage.get_balance(user_id)} GRAM*",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Промокод уже использован или недействителен!")
