import logging
import sys
from pathlib import Path
from telegram.ext import filters
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import Config
from src.models.storage import Storage
from src.services.game_service import GameService
from src.handlers.game_handlers import GameHandlers

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting casino bot...")
    
    storage = Storage(Config.DATA_PATH)
    game_service = GameService(storage)
    handlers = GameHandlers(storage, game_service)
    
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Команды для всех (только латиница!)
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("balance", handlers.balance))
    application.add_handler(CommandHandler("transfer", handlers.transfer))
    application.add_handler(CommandHandler("mines", handlers.mines_game))
    application.add_handler(CommandHandler("joker", handlers.joker_game))
    application.add_handler(CommandHandler("coinflip", handlers.coinflip_game))
    application.add_handler(CommandHandler("top", handlers.top_players))
    
    # Админ-команды
    application.add_handler(CommandHandler("add", handlers.admin_add_balance))
    application.add_handler(CommandHandler("promo", handlers.admin_create_promo))
    application.add_handler(CommandHandler("userbal", handlers.admin_balance))
    application.add_handler(CommandHandler("allbalances", handlers.admin_all_balances))
    application.add_handler(CommandHandler("setbalance", handlers.admin_set_balance))
    
    # Промокоды через #
    application.add_handler(CommandHandler("promocode", handlers.promo_code))
    

    application.add_handler(CommandHandler("take", handlers.admin_take_balance))  # <-- новая
    application.add_handler(CommandHandler("ban", handlers.admin_ban))            # <-- новая
    application.add_handler(CommandHandler("unban", handlers.admin_unban))        # <-- новая
    application.add_handler(CommandHandler("banned", handlers.admin_banned_list)) # <-- новая
    
    # Callback для кнопок
    application.add_handler(CallbackQueryHandler(handlers.coinflip_callback, pattern="^coinflip_"))
    application.add_handler(CallbackQueryHandler(handlers.mines_callback, pattern="^mines_"))


    # После всех CommandHandler добавь:
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_text))
    logger.info("Bot started! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
