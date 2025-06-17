#!/usr/bin/env python3
"""
Тестовая программа для проверки гибридной Globalping интеграции
"""

from globalping_hybrid_client import GlobalpingHybridClient, hybrid_ping, hybrid_http

def test_hybrid_client():
    """Тестирует гибридный клиент с fallback"""
    
    print("🧪 Тестирование Globalping Hybrid Client")
    print("=" * 50)
    
    # Тестовые цели
    targets = [
        "google.com",
        "github.com",
        "8.8.8.8"
    ]
    
    for target in targets:
        print(f"\n🎯 Тестирование: {target}")
        print("-" * 30)
        
        # Тест 1: Гибридный ping
        print("📡 Hybrid Ping тест:")
        ping_result = hybrid_ping(target)
        print(ping_result[:300] + "..." if len(ping_result) > 300 else ping_result)
        
        # Тест 2: Гибридный HTTP (только для веб-ресурсов)
        if not target.replace(".", "").isdigit():  # Не IP адрес
            print(f"\n🌐 Hybrid HTTP тест:")
            http_result = hybrid_http(target)
            print(http_result[:300] + "..." if len(http_result) > 300 else http_result)
        
        print("\n" + "="*50)

def test_direct_hybrid():
    """Тестирует прямое использование гибридного клиента"""
    
    print("\n🔧 Прямое тестирование Hybrid клиента")
    print("=" * 50)
    
    # Тестируем с предпочтением MCP (по умолчанию)
    print("1️⃣ Клиент с предпочтением MCP:")
    client_mcp = GlobalpingHybridClient(prefer_mcp=True)
    
    result = client_mcp.ping("google.com", "EU,NA")
    print(f"Ping результат: {result['success']}")
    if result['success']:
        print(f"Источник: {result.get('source', 'Unknown')}")
        print(result['result'][:150] + "...")
    else:
        print(f"Ошибка: {result['error']}")
    
    print("\n" + "-"*30)
    
    # Тестируем только REST API
    print("2️⃣ Клиент только с REST API:")
    client_rest = GlobalpingHybridClient(prefer_mcp=False)
    
    result = client_rest.ping("google.com", "EU,NA")
    print(f"Ping результат: {result['success']}")
    if result['success']:
        print(f"Источник: {result.get('source', 'Unknown')}")
        print(result['result'][:150] + "...")
    else:
        print(f"Ошибка: {result['error']}")

def test_fallback_behavior():
    """Тестирует поведение fallback"""
    
    print("\n🔄 Тестирование fallback поведения")
    print("=" * 50)
    
    client = GlobalpingHybridClient(prefer_mcp=True)
    
    print("Попытка ping с автоматическим fallback...")
    result = client.ping("cloudflare.com", "EU")
    
    if result['success']:
        source = result.get('source', 'Unknown')
        if 'REST API' in source:
            print("✅ Fallback к REST API работает!")
        elif 'MCP' in source:
            print("✅ MCP сервер работает!")
        else:
            print(f"✅ Тест прошел через: {source}")
        
        print(f"Результат: {result['result'][:100]}...")
    else:
        print(f"❌ Оба метода не сработали: {result['error']}")

if __name__ == "__main__":
    try:
        test_hybrid_client()
        test_direct_hybrid()
        test_fallback_behavior()
        
        print("\n✅ Тестирование завершено!")
        print("\n💡 Обратите внимание:")
        print("- Если видите 'REST API' в источниках - MCP сервер недоступен, используется fallback")
        print("- Если видите 'MCP' - официальный MCP сервер работает")
        print("- Гибридный подход обеспечивает надежность работы")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("Убедитесь, что файл globalping_hybrid_client.py находится в той же папке")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        print("Проверьте подключение к интернету") 