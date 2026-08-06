from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import logging
import re
import random
import asyncio

logger = logging.getLogger(__name__)

class GameHandlers:
    def __init__(self, storage, game_service):
        self.storage = storage
        self.game_service = game_service

    async def _check_banned(self, update: Update) -> bool:
        """Проверка бана пользователя"""
        user_id = update.effective_user.id
        if self.storage.is_banned(user_id):
            await update.message.reply_text(
                "🚫 Вы забанены в этом боте!\n"
                "❌ Вы не можете использовать команды.\n"
                "Для снятия бана обратитесь к администратору."
            )
            return True
        return False

    # ===== КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ =====

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.storage.create_user(user.id, user.username, user.first_name)
        await update.message.reply_text(
            f"*Привет, {user.first_name}!*\n\n"
            f"Я бот-казино для вашего чата!\n"
            f"Твой баланс: *{self.storage.format_balance(self.storage.get_balance(user.id))} GRAM*\n\n"
            f"Используй /help для списка команд",
            parse_mode='Markdown'
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
• `/promocode КОД` - активировать промокод

🏆 *ТОП:*
• `/top` - топ игроков в чате

👑 *АДМИН-КОМАНДЫ:*
• `/add [ID] [сумма]` - выдать GRAM
• `/take [ID] [сумма]` - забрать GRAM
• `/ban [ID]` - забанить пользователя
• `/unban [ID]` - снять бан
• `/banned` - список забаненных
• `/promo [код] [сумма] [кол-во]` - создать промокод

💰 Твой баланс: *{} GRAM*
""".format(self.storage.format_balance(self.storage.get_balance(update.effective_user.id)))
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать баланс (/balance)"""
        if await self._check_banned(update):
            return
        user = update.effective_user
        balance = self.storage.get_balance(user.id)
        await update.message.reply_text(
            f"Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
            parse_mode='Markdown'
        )

    async def transfer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Перевод средств (/transfer)"""
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
            await update.message.reply_text(
                f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(sender_balance)} GRAM*",
                parse_mode='Markdown'
            )
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
        
        await update.message.reply_text(
            f"*Перевод выполнен!*\n\n"
            f"Переведено: *{self.storage.format_balance(amount)} GRAM*\n"
            f"Твой баланс: *{self.storage.format_balance(self.storage.get_balance(sender_id))} GRAM*",
            parse_mode='Markdown'
        )

    async def mines_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Игра в мины (/mines)"""
        if await self._check_banned(update):
            return
        if not context.args:
            await update.message.reply_text("❌ Использование: `/mines [сумма]` или `мины [сумма]`")
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
            await update.message.reply_text(
                f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
                parse_mode='Markdown'
            )
            return
    
        # Генерируем поле 5x5
        field = []
        mines_positions = random.sample(range(25), 5)
    
        for i in range(25):
            if i in mines_positions:
                field.append('💣')
            else:
                multipliers = [1.5, 2.0, 2.5, 3.0, 3.5, 5.0]
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
    
        keyboard.append([InlineKeyboardButton("Забрать выигрыш", callback_data=f"mines_take_{amount}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
    
        # Сохраняем состояние игры
        context.user_data['mines_game'] = {
            'amount': amount,
            'field': field,
            'revealed': [],
            'message_id': None,
            'chat_id': update.effective_chat.id
        }
    
        msg = await update.message.reply_text(
            f"*Минное поле*\n\n"
            f"Ставка: *{self.storage.format_balance(amount)} GRAM*\n"
            f"Найди 3 безопасные клетки!\n\n"
            f"*Поле 5×5:*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
        context.user_data['mines_game']['message_id'] = msg.message_id

    async def mines_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кликов по полю в минах"""
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
            await query.answer("Эта клетка уже открыта!")
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
        
            text = f"*БАХ! Ты наступил на мину!*\n\n"
            for i in range(0, 25, 5):
                text += ' '.join(display[i:i+5]) + '\n'
            text += f"\nПроигрыш: *{self.storage.format_balance(amount)} GRAM*\n"
            text += f"Новый баланс: *{self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*"
        
            await query.edit_message_text(text, parse_mode='Markdown')
            context.user_data.pop('mines_game', None)
            return
    
        # Безопасная клетка - считаем накопленный выигрыш
        current_win = amount
        for idx in revealed:
            val = field[idx]
            if val != '💣':
                try:
                    current_win = current_win * float(val.replace('×', ''))
                except:
                    pass
        win_amount = int(current_win)
        revealed_count = len(revealed)
        multiplier = win_amount / amount
    
        # Проверяем - открыто 3 клетки или больше
        if revealed_count >= 3:
            # Автоматический выигрыш
            self.storage.update_balance(user_id, win_amount, 'win', 'mines', f'Выиграл в мины: накопление множителей')
        
            display = []
            for i in range(25):
                if i in revealed:
                    display.append(field[i])
                elif field[i] == '💣':
                    display.append('❓')
                else:
                    display.append('❓')
        
            multipliers_list = []
            for i in revealed:
                if field[i] != '💣':
                    multipliers_list.append(field[i].replace('×', '×'))
            multipliers_text = " → ".join(multipliers_list)
        
            text = f"*Поздравляю! Ты выиграл!*\n\n"
            for i in range(0, 25, 5):
                text += ' '.join(display[i:i+5]) + '\n'
            text += f"\nСтавка: *{self.storage.format_balance(amount)} GRAM*\n"
            text += f"Множители: *{multipliers_text}*\n"
            text += f"Выигрыш: *{self.storage.format_balance(win_amount)} GRAM*\n"
            text += f"Чистая прибыль: *{self.storage.format_balance(win_amount - amount)} GRAM*\n"
            text += f"Новый баланс: *{self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*"
        
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
    
        multipliers_list = []
        for i in revealed:
            if field[i] != '💣':
                multipliers_list.append(field[i].replace('×', '×'))
        multipliers_text = " → ".join(multipliers_list)
    
        text = f"*Минное поле*\n\n"
        text += f"Ставка: *{self.storage.format_balance(amount)} GRAM*\n"
        text += f"Открыто клеток: *{revealed_count}/3*\n"
        text += f"Множители: *{multipliers_text}*\n"
        text += f"Потенциальный выигрыш: *{self.storage.format_balance(win_amount)} GRAM*\n\n"
    
        for i in range(0, 25, 5):
            text += ' '.join(display[i:i+5]) + '\n'
    
        await query.edit_message_text(
            text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
        context.user_data['mines_game'] = game_state

    async def mines_take_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Забрать выигрыш' в минах - множители накапливаются"""
        query = update.callback_query
        await query.answer()
    
        data = query.data.split('_')
        user_id = update.effective_user.id
    
        if self.storage.is_banned(user_id):
            await query.edit_message_text("🚫 Вы забанены!")
            return
    
        if len(data) < 3:
            await query.edit_message_text("❌ Ошибка в данных")
            return
    
        try:
            amount = int(data[2])
        except ValueError:
            await query.edit_message_text("❌ Ошибка: неверная сумма")
            return
    
        game_state = context.user_data.get('mines_game', {})
        field = game_state.get('field', [])
        revealed = game_state.get('revealed', [])
    
        if not field:
            await query.edit_message_text("❌ Игра не найдена. Начни заново.")
            return
    
        if not revealed:
            await query.edit_message_text("❌ Открой хотя бы одну клетку, чтобы забрать выигрыш!")
            return
    
        # Считаем выигрыш по принципу НАКОПЛЕНИЯ множителей
        current_win = amount
        for idx in revealed:
            val = field[idx]
            if val != '💣':
                try:
                    current_win = current_win * float(val.replace('×', ''))
                except:
                    pass
    
        win_amount = int(current_win)
    
        self.storage.update_balance(user_id, win_amount, 'win', 'mines', f'Забрал выигрыш: накопление множителей')
    
        display = []
        for i in range(25):
            if i in revealed:
                display.append(field[i])
            elif field[i] == '💣':
                display.append('❓')
            else:
                display.append('❓')
    
        # Показываем все открытые множители
        multipliers_list = []
        for i in revealed:
            if field[i] != '💣':
                multipliers_list.append(field[i].replace('×', '×'))
        multipliers_text = " → ".join(multipliers_list)
    
        text = f"*Ты забрал выигрыш!*\n\n"
        for i in range(0, 25, 5):
            text += ' '.join(display[i:i+5]) + '\n'
        text += f"\nСтавка: *{self.storage.format_balance(amount)} GRAM*\n"
        text += f"Множители: *{multipliers_text}*\n"
        text += f"Выигрыш: *{self.storage.format_balance(win_amount)} GRAM*\n"
        text += f"Чистая прибыль: *{self.storage.format_balance(win_amount - amount)} GRAM*\n"
        text += f"Новый баланс: *{self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*"
    
        await query.edit_message_text(text, parse_mode='Markdown')
        context.user_data.pop('mines_game', None)

    async def joker_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Игра Джокер (слот-машина)"""
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
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            await update.message.reply_text(
                f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
                parse_mode='Markdown'
            )
            return
        
        # Показываем крутящиеся слоты
        slots_message = await update.message.reply_text(
            "🎰 *Крутим слоты...*\n\n"
            "┌───┬───┬───┐\n"
            "│ 🎲 │ 🎲 │ 🎲 │\n"
            "└───┴───┴───┘\n\n"
            "🌀 *Загрузка...*",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(1.5)
        
        result = self.game_service.joker(user_id, amount)

        if not result['success']:
            await slots_message.edit_text(f"❌ {result['message']}")
            return
        
        keyboard = [
            [InlineKeyboardButton("Крутить еще раз", callback_data=f"joker_again_{amount}")],
            [InlineKeyboardButton("Баланс", callback_data="show_balance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await slots_message.edit_text(
            f"{result['message']}\n\n"
            f"*Новый баланс: {self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def joker_again_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Крутить еще раз'"""
        query = update.callback_query
        await query.answer()
    
        data = query.data.split('_')
        if len(data) < 3:
            await query.edit_message_text("❌ Ошибка в данных")
            return
    
        amount = int(data[2])
        user_id = update.effective_user.id
    
        if self.storage.is_banned(user_id):
            await query.edit_message_text("🚫 Вы забанены!")
            return
    
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            await query.edit_message_text(
                f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
                parse_mode='Markdown'
            )
            return
    
        # Показываем крутящиеся слоты
        await query.edit_message_text(
            "🎰 *Крутим слоты...*\n\n"
            "┌───┬───┬───┐\n"
            "│ 🎲 │ 🎲 │ 🎲 │\n"
            "└───┴───┴───┘\n\n"
            "🌀 *Загрузка...*",
            parse_mode='Markdown'
        )
    
        await asyncio.sleep(1.2)
    
        result = self.game_service.joker(user_id, amount)
    
        keyboard = [
            [InlineKeyboardButton("Крутить еще раз", callback_data=f"joker_again_{amount}")],
            [InlineKeyboardButton("Баланс", callback_data="show_balance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
        await query.edit_message_text(
            f"{result['message']}\n\n"
            f"*Новый баланс: {self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def coinflip_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Игра Орёл/Решка (/coinflip)"""
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
        
        user_id = update.effective_user.id
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            await update.message.reply_text(
                f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
                parse_mode='Markdown'
            )
            return
        
        keyboard = [
            [
                InlineKeyboardButton("Орел", callback_data=f"coinflip_орел_{amount}"),
                InlineKeyboardButton("Решка", callback_data=f"coinflip_решка_{amount}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"*Сделай выбор!*\n\n"
            f"Ставка: *{self.storage.format_balance(amount)} GRAM*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def coinflip_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора в Орёл/Решка"""
        query = update.callback_query
        await query.answer()
        
        data = query.data.split('_')
        if len(data) != 3:
            await query.edit_message_text("❌ Ошибка в данных")
            return
        
        choice = data[1]
        amount = int(data[2])
        user_id = update.effective_user.id
        
        if self.storage.is_banned(user_id):
            await query.edit_message_text("🚫 Вы забанены!")
            return
        
        result = self.game_service.coinflip(user_id, amount, choice)
        
        keyboard = [
            [InlineKeyboardButton("Еще раз", callback_data=f"coinflip_again_{amount}")],
            [InlineKeyboardButton("Баланс", callback_data="show_balance")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"{result['message']}\n\n"
            f"*Новый баланс: {self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def coinflip_again_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки 'Еще раз' в Орёл/Решка"""
        query = update.callback_query
        await query.answer()
        
        data = query.data.split('_')
        if len(data) < 3:
            await query.edit_message_text("❌ Ошибка в данных")
            return
        
        amount = int(data[2])
        user_id = update.effective_user.id
        
        if self.storage.is_banned(user_id):
            await query.edit_message_text("🚫 Вы забанены!")
            return
        
        balance = self.storage.get_balance(user_id)
        if balance < amount:
            await query.edit_message_text(
                f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
                parse_mode='Markdown'
            )
            return
        
        keyboard = [
            [
                InlineKeyboardButton("Орел", callback_data=f"coinflip_орел_{amount}"),
                InlineKeyboardButton("Решка", callback_data=f"coinflip_решка_{amount}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"*Сделай выбор!*\n\n"
            f"Ставка: *{self.storage.format_balance(amount)} GRAM*",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def top_players(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Топ игроков (/top)"""
        if await self._check_banned(update):
            return
        top = self.storage.get_top_players(10)
        if not top:
            await update.message.reply_text("Пока нет игроков в топе")
            return
        
        text = "🏆 *Топ игроков чата:*\n\n"
        medals = ['🥇', '🥈', '🥉']
        for i, player in enumerate(top, 1):
            medal = medals[i-1] if i <= 3 else f'{i}.'
            name = player.get('first_name') or player.get('username') or f"User{player['user_id']}"
            text += f"{medal} *{name}* - *{self.storage.format_balance(player['balance'])} GRAM* (🎮 {player['games_played']} игр)\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def promo_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Активация промокода через команду /promocode"""
        if await self._check_banned(update):
            return
        
        if not context.args:
            await update.message.reply_text("❌ Использование: `/promocode КОД` или `#КОД`")
            return
        
        code = context.args[0].lstrip('#')
        user_id = update.effective_user.id
        
        # Проверяем существует ли промокод
        if not self.storage._is_promo_exists(code):
            await update.message.reply_text("❌ Недействительный промокод!")
            return
        
        # Получаем информацию о промокоде
        promo_info = self.storage.get_promo_info(code)
        if not promo_info:
            await update.message.reply_text("❌ Промокод не найден")
            return
        
        # Пробуем активировать
        amount = self.storage.use_promo_code(code, user_id)
        if amount:
            self.storage.update_balance(user_id, amount, 'promo', None, f'Активирован промокод {code}')
            await update.message.reply_text(
                f"*Промокод активирован!*\n\n"
                f"Получено: *{self.storage.format_balance(amount)} GRAM*\n"
                f"Осталось использований: *{promo_info['remaining'] - 1}*\n"
                f"Твой баланс: *{self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*",
                parse_mode='Markdown'
            )
        else:
            # Проверяем почему не активировался
            if promo_info['remaining'] <= 0:
                await update.message.reply_text("❌ Промокод уже использован максимальное количество раз!")
            else:
                promo = self.storage.data['promo_codes'].get(code.upper())
                if str(user_id) in promo.get('used_by', []):
                    await update.message.reply_text("❌ Вы уже использовали этот промокод!")
                else:
                    await update.message.reply_text("❌ Не удалось активировать промокод!")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений (промокоды через #)"""
        # Если это не текстовое сообщение — выходим
        if not update.message or not update.message.text:
            return
    
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
        
            # Получаем информацию о промокоде
            promo_info = self.storage.get_promo_info(code)
            if not promo_info:
                await update.message.reply_text("❌ Промокод не найден")
                return
        
            # Пробуем активировать
            amount = self.storage.use_promo_code(code, user_id)
            if amount:
                self.storage.update_balance(user_id, amount, 'promo', None, f'Активирован промокод {code}')
                await update.message.reply_text(
                    f"*Промокод активирован!*\n\n"
                    f"Получено: *{self.storage.format_balance(amount)} GRAM*\n"
                    f"Осталось использований: *{promo_info['remaining'] - 1}*\n"
                    f"Твой баланс: *{self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*",
                    parse_mode='Markdown'
                )
            else:
                if promo_info['remaining'] <= 0:
                    await update.message.reply_text("❌ Промокод уже использован максимальное количество раз!")
                else:
                    promo = self.storage.data['promo_codes'].get(code.upper())
                    if str(user_id) in promo.get('used_by', []):
                        await update.message.reply_text("❌ Вы уже использовали этот промокод!")
                    else:
                        await update.message.reply_text("❌ Не удалось активировать промокод!")

    # ===== АДМИН-КОМАНДЫ =====

    async def admin_add_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Выдать GRAM пользователю (/add)"""
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 2 and not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Использование:\n"
                "/add [ID] [сумма]\n"
                "Или ответь на сообщение: /add [сумма]"
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
        
        self.storage.update_balance(recipient_id, amount, 'admin_gift', None, f'Админ выдал {amount} GRAM')
        await update.message.reply_text(
            f"*Выдано {self.storage.format_balance(amount)} GRAM*\n"
            f"Новый баланс: *{self.storage.format_balance(self.storage.get_balance(recipient_id))} GRAM*",
            parse_mode='Markdown'
        )
    
    async def admin_take_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Забрать GRAM у пользователя (/take)"""
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 2 and not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Использование: /take [ID] [сумма]\n"
                "Или ответь на сообщение: /take [сумма]"
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
                f"Баланс: *{self.storage.format_balance(current_balance)} GRAM*\n"
                f"Запрошено: *{self.storage.format_balance(amount)} GRAM*",
                parse_mode='Markdown'
            )
            return
        
        self.storage.update_balance(recipient_id, -amount, 'admin_take', None, f'Админ забрал {amount} GRAM')
        self.storage.add_to_treasury(amount)
        
        user_info = self.storage.get_user(recipient_id)
        user_name = user_info.get('first_name', 'Пользователь') if user_info else 'Пользователь'
        
        await update.message.reply_text(
            f"*Забрано {self.storage.format_balance(amount)} GRAM* у пользователя *{user_name}*\n"
            f"Новый баланс: *{self.storage.format_balance(self.storage.get_balance(recipient_id))} GRAM*\n"
            f"В казне: *{self.storage.format_balance(self.storage.get_treasury())} GRAM*",
            parse_mode='Markdown'
        )
        
        try:
            await context.bot.send_message(
                recipient_id,
                f"Админ забрал у тебя {self.storage.format_balance(amount)} GRAM!\n"
                f"Твой баланс: *{self.storage.format_balance(self.storage.get_balance(recipient_id))} GRAM*",
                parse_mode='Markdown'
            )
        except:
            pass
    
    async def admin_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Забанить пользователя (/ban)"""
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 1 and not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Использование: /ban [ID]\n"
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
                f"*Пользователь {user_name} забанен!*\n"
                f"ID: `{recipient_id}`\n"
                f"Он больше не сможет пользоваться ботом",
                parse_mode='Markdown'
            )
            
            try:
                await context.bot.send_message(
                    recipient_id,
                    "*Вы были забанены в боте-казино!*\n"
                    "Вы больше не можете пользоваться ботом.\n"
                    "Для снятия бана обратитесь к администратору.",
                    parse_mode='Markdown'
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка при бане пользователя")
    
    async def admin_unban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Снять бан с пользователя (/unban)"""
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        if len(context.args) < 1 and not update.message.reply_to_message:
            await update.message.reply_text(
                "❌ Использование: /unban [ID]\n"
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
                f"*Бан снят с пользователя {user_name}*\n"
                f"ID: `{recipient_id}`\n"
                f"Пользователь снова может пользоваться ботом",
                parse_mode='Markdown'
            )
            
            try:
                await context.bot.send_message(
                    recipient_id,
                    "*Администратор снял с вас бан!*\n"
                    "Вы снова можете пользоваться ботом.",
                    parse_mode='Markdown'
                )
            except:
                pass
        else:
            await update.message.reply_text("❌ Ошибка при разбане пользователя")
    
    async def admin_banned_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список забаненных пользователей (/banned)"""
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        banned_users = self.storage.get_banned_users()
        if not banned_users:
            await update.message.reply_text("🚫 Нет забаненных пользователей")
            return
        
        text = "🔨 *Список забаненных пользователей:*\n\n"
        for user in banned_users:
            name = user.get('first_name') or user.get('username') or f"User{user['user_id']}"
            text += f"*{name}* (ID: `{user['user_id']}`)\n"
            text += f"Баланс: *{self.storage.format_balance(user['balance'])} GRAM*\n"
            text += f"Игр: *{user['games_played']}*\n"
            text += "—" * 30 + "\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def admin_create_promo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Создать промокод (/promo)"""
        from config import Config
        user_id = update.effective_user.id
    
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
    
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Использование: `/promo [код] [сумма] [количество_использований]`\n"
                "Пример: `/promo BONUS 5000 10`\n"
                "Если не указать количество - будет 1 использование"
            )
            return
    
        code = context.args[0].upper()
        try:
            amount = int(context.args[1])
        except:
            await update.message.reply_text("❌ Введи корректную сумму")
            return
    
        max_uses = 1
        if len(context.args) >= 3:
            try:
                max_uses = int(context.args[2])
            except:
                await update.message.reply_text("❌ Введи корректное количество использований")
                return
    
        if amount <= 0 or max_uses <= 0:
            await update.message.reply_text("❌ Сумма и количество использований должны быть положительными")
            return
    
        self.storage.create_promo_code(code, amount, max_uses)
    
        await update.message.reply_text(
            f"*Промокод создан!*\n\n"
            f"Код: `#{code}`\n"
            f"Сумма: *{self.storage.format_balance(amount)} GRAM*\n"
            f"Использований: *{max_uses}*\n"
            f"\nИспользование: `#{code}` или `/promocode {code}`",
            parse_mode='Markdown'
        )
    
    async def admin_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверить баланс пользователя (/userbal)"""
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
            f"Пользователь: *{user_info.get('first_name', 'Unknown')}*\n"
            f"ID: `{target_id}`\n"
            f"Баланс: *{self.storage.format_balance(user_info['balance'])} GRAM*\n"
            f"Игр сыграно: *{user_info['games_played']}*",
            parse_mode='Markdown'
        )
    
    async def admin_all_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Все пользователи с балансами (/allbalances)"""
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
            text += f"{i}. *{name}* - *{self.storage.format_balance(user['balance'])} GRAM*\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def admin_set_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установить баланс пользователя (/setbalance)"""
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
        
        await update.message.reply_text(
            f"*Баланс обновлен!*\n"
            f"Новый баланс: *{self.storage.format_balance(new_balance)} GRAM*",
            parse_mode='Markdown'
        )
    
    async def admin_treasury(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать казну чата (/treasury)"""
        from config import Config
        user_id = update.effective_user.id
        
        if user_id not in Config.ADMIN_IDS:
            await update.message.reply_text("❌ У тебя нет прав для этой команды!")
            return
        
        treasury = self.storage.get_treasury()
        total_users = len(self.storage.get_all_users())
        banned_users = len(self.storage.get_banned_users())
        
        await update.message.reply_text(
            f"*Казна чата*\n\n"
            f"*Всего в казне: *{self.storage.format_balance(treasury)} GRAM*\n\n"
            f"Статистика:\n"
            f"• Пользователей: *{total_users}*\n"
            f"• Забаненных: *{banned_users}*",
            parse_mode='Markdown'
        )

    # ===== ОБЩИЙ ОБРАБОТЧИК CALLBACK =====

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Общий обработчик callback'ов для кнопок"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if self.storage.is_banned(user_id):
            await query.edit_message_text("🚫 Вы забанены!")
            return
        
        if data == "show_balance":
            balance = self.storage.get_balance(user_id)
            keyboard = [[InlineKeyboardButton("🎮 Играть", callback_data="show_games")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"*Баланс: {self.storage.format_balance(balance)} GRAM*",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        elif data == "show_games":
            keyboard = [
                [InlineKeyboardButton("Мины", callback_data="game_mines")],
                [InlineKeyboardButton("Джокер", callback_data="game_joker")],
                [InlineKeyboardButton("Орёл/Решка", callback_data="game_coinflip")],
                [InlineKeyboardButton("Баланс", callback_data="show_balance")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "🎮 *Выбери игру:*",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        elif data == "show_top":
            top = self.storage.get_top_players(10)
            if not top:
                await query.edit_message_text("Пока нет игроков в топе")
                return
            
            text = "🏆 *Топ игроков чата:*\n\n"
            medals = ['🥇', '🥈', '🥉']
            for i, player in enumerate(top, 1):
                medal = medals[i-1] if i <= 3 else f'{i}.'
                name = player.get('first_name') or player.get('username') or f"User{player['user_id']}"
                text += f"{medal} *{name}* - *{self.storage.format_balance(player['balance'])} GRAM*\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="show_games")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
        elif data.startswith("joker_again_"):
            amount = int(data.split('_')[2])
            balance = self.storage.get_balance(user_id)
            if balance < amount:
                await query.edit_message_text(
                    f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
                    parse_mode='Markdown'
                )
                return
            
            await query.edit_message_text(
                "🎰 *Крутим слоты...*\n\n"
                "┌───┬───┬───┐\n"
                "│ 🎲 │ 🎲 │ 🎲 │\n"
                "└───┴───┴───┘\n\n"
                "🌀 *Загрузка...*",
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(1.2)
            
            result = self.game_service.joker(user_id, amount)
            
            keyboard = [
                [InlineKeyboardButton("Крутить еще раз", callback_data=f"joker_again_{amount}")],
                [InlineKeyboardButton("Баланс", callback_data="show_balance")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"{result['message']}\n\n"
                f"*Новый баланс: {self.storage.format_balance(self.storage.get_balance(user_id))} GRAM*",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        elif data.startswith("coinflip_again_"):
            amount = int(data.split('_')[2])
            balance = self.storage.get_balance(user_id)
            if balance < amount:
                await query.edit_message_text(
                    f"❌ Недостаточно средств! Твой баланс: *{self.storage.format_balance(balance)} GRAM*",
                    parse_mode='Markdown'
                )
                return
            
            keyboard = [
                [
                    InlineKeyboardButton("Орел", callback_data=f"coinflip_орел_{amount}"),
                    InlineKeyboardButton("Решка", callback_data=f"coinflip_решка_{amount}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"*Сделай выбор!*\n\n"
                f"Ставка: *{self.storage.format_balance(amount)} GRAM*",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        elif data.startswith("game_"):
            game = data.replace("game_", "")
            if game == "mines":
                await query.edit_message_text(
                    "💣 *Мины*\n\n"
                    "Используй команду: `/mines [сумма]` или `мины [сумма]`",
                    parse_mode='Markdown'
                )
            elif game == "joker":
                await query.edit_message_text(
                    "🎰 *Джокер*\n\n"
                    "Используй команду: `/joker [сумма]`",
                    parse_mode='Markdown'
                )
            elif game == "coinflip":
                await query.edit_message_text(
                    "🪙 *Орёл/Решка*\n\n"
                    "Используй команду: `/coinflip [сумма]`",
                    parse_mode='Markdown'
                )
