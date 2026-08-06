import subprocess
import sys
import os


try:
    import telegram
except:
    print("Устанавливаю зависимости...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot", "python-dotenv"])


os.system("python3 main.py")
