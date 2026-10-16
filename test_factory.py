import asyncio
from config import FACTORY_BOT_TOKEN
from telegram_adapter import TelegramAdapter

async def main():
    a = TelegramAdapter(FACTORY_BOT_TOKEN, timeout=10)
    await a.init()
    result = await a.get_me()
    await a.close()
    print(result)

asyncio.run(main())
