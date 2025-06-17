# -*- coding: utf-8 -*-
"""
Тест для Globalping Token Client
"""

import os
from dotenv import load_dotenv
from globalping_with_token import GlobalpingTokenClient, token_ping

load_dotenv()

def test_token():
    """Тестирует клиент с токеном"""
    token = os.getenv("GLOBALPING_API_TOKEN")
    
    if not token:
        print("❌ Токен GLOBALPING_API_TOKEN не найден в .env файле")
        print("📝 Добавьте токен в .env файл:")
        print("GLOBALPING_API_TOKEN=your-token-here")
        print()
        print("🔗 Получить токен: https://www.globalping.io/")
        return False
    
    print(f"🔑 Найден токен: {token[:10]}...")
    
    try:
        # Проверяем кредиты
        client = GlobalpingTokenClient(token)
        credits = client.get_credits()
        
        if credits["success"]:
            print(f"💰 Кредиты: {credits['credits']}")
        
        # Тестируем ping
        print("\n🧪 Тестирую ping google.com...")
        result = client.ping("google.com", "EU", 2)
        
        if result["success"]:
            print("✅ Ping тест УСПЕШЕН!")
            print(result["result"])
            return True
        else:
            print(f"❌ Ping тест провалился: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    print("🔑 Тестирование Globalping Token Client")
    print("=" * 60)
    test_token() 