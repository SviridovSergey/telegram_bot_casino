from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
import logging
import re

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
        user = update.effective_user
        balance = self.storage.get_balance(user.id)
        await update.message.reply_text(f"Твой баланс: {balance} GRAM")

    async def transfer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        result = self.game_service.mines(user_id, amount)
        
        if not result['success']:
            await update.message.reply_text(f"❌ {result['message']}")
            return
        
        await update.message.reply_text(
            f"{result['message']}\n"
            f"Твой новый баланс: {self.storage.get_balance(user_id)} GRAM"
        )

    async def joker_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    async def coinflip_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
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

