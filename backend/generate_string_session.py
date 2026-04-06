from telethon.sync import TelegramClient
from telethon.sessions import StringSession


api_id = int(input("API_ID: ").strip())
api_hash = input("API_HASH: ").strip()

with TelegramClient(StringSession(), api_id, api_hash) as client:
    print("\nTELEGRAM_SESSION_STRING (copie inteira para o Render):\n")
    print(client.session.save())
