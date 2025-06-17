#!/usr/bin/env python3
"""
Тестовая программа для проверки Globalping MCP интеграции
"""

from globalping_mcp_client import GlobalpingMCPClient, quick_ping, quick_http, comprehensive_test

def test_mcp_client():
    """Тестирует основные функции MCP клиента"""
    
    print("🧪 Тестирование Globalping MCP Client")
    print("=" * 50)
    
    # Тестовые цели
    targets = [
        "google.com",
        "https://github.com",
        "8.8.8.8"
    ]
    
    for target in targets:
        print(f"\n🎯 Тестирование: {target}")
        print("-" * 30)
        
        # Тест 1: Быстрый ping
        print("📡 Ping тест:")
        ping_result = quick_ping(target)
        print(ping_result[:200] + "..." if len(ping_result) > 200 else ping_result)
        
        # Тест 2: HTTP тест (только для веб-ресурсов)
        if not target.replace(".", "").isdigit():  # Не IP адрес
            print("\n🌐 HTTP тест:")
            http_result = quick_http(target)
            print(http_result[:200] + "..." if len(http_result) > 200 else http_result)
        
        print("\n" + "="*50)

def test_direct_mcp():
    """Тестирует прямое использование MCP клиента"""
    
    print("\n🔧 Прямое тестирование MCP клиента")
    print("=" * 50)
    
    client = GlobalpingMCPClient()
    
    # Тест ping
    result = client.ping("google.com", "EU,NA")
    print(f"Ping результат: {result['success']}")
    if result['success']:
        print(result['result'][:150] + "...")
    else:
        print(f"Ошибка: {result['error']}")
    
    # Тест locations
    print("\n📍 Получение локаций:")
    locations = client.get_locations()
    print(f"Локации результат: {locations['success']}")
    if locations['success']:
        print(locations['result'][:150] + "...")

if __name__ == "__main__":
    try:
        test_mcp_client()
        test_direct_mcp()
        
        print("\n✅ Тестирование завершено!")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("Убедитесь, что файл globalping_mcp_client.py находится в той же папке")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        print("Проверьте подключение к интернету и доступность MCP сервера") 