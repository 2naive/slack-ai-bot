#!/usr/bin/env python3
"""
Продвинутый тест для исправленного Globalping MCP клиента
"""

from globalping_mcp_client import GlobalpingMCPClient
import requests
import json

def test_mcp_endpoints():
    """Тестирует различные MCP эндпоинты"""
    
    print("🔍 Тестирование MCP эндпоинтов Globalping...")
    print("=" * 50)
    
    endpoints = [
        "https://mcp.globalping.dev/sse",
        "https://mcp.globalping.dev/api", 
        "https://mcp.globalping.dev",
        "https://api.globalping.io/mcp"
    ]
    
    # Простой запрос для проверки доступности
    test_requests = [
        {
            "name": "tools/list",
            "data": {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list"
            }
        },
        {
            "name": "initialize", 
            "data": {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "GlobalpingMCPClient",
                        "version": "2.0"
                    }
                }
            }
        }
    ]
    
    working_endpoints = []
    
    for endpoint in endpoints:
        print(f"\n🎯 Тестирование: {endpoint}")
        
        for req in test_requests:
            print(f"  Запрос: {req['name']}")
            
            headers = {
                "Content-Type": "application/json", 
                "Accept": "application/json",
                "User-Agent": "GlobalpingMCPClient/2.0"
            }
            
            try:
                response = requests.post(
                    endpoint,
                    json=req['data'],
                    headers=headers,
                    timeout=10
                )
                
                print(f"  Статус: {response.status_code}")
                
                if response.status_code == 200:
                    print("  ✅ Успешный ответ!")
                    working_endpoints.append(endpoint)
                    try:
                        result = response.json()
                        if "result" in result:
                            print(f"  Данные: {str(result['result'])[:100]}...")
                    except:
                        pass
                    break
                elif response.status_code == 401:
                    print("  ❌ 401 - Нужна аутентификация") 
                elif response.status_code == 404:
                    print("  ❌ 404 - Эндпоинт не найден")
                else:
                    print(f"  ❌ {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                print(f"  ❌ Ошибка: {str(e)[:50]}...")
    
    print(f"\n📊 Рабочие эндпоинты: {working_endpoints}")
    return working_endpoints

def test_improved_client():
    """Тестирует улучшенный MCP клиент"""
    
    print("\n🔧 Тестирование улучшенного MCP клиента...")
    print("=" * 50)
    
    # Создаем клиент
    client = GlobalpingMCPClient()
    
    # Тестируем ping
    print("📡 Тест ping:")
    result = client.ping("google.com", "EU", 2)
    
    print(f"Успех: {result['success']}")
    if result['success']:
        print("✅ MCP PING работает!")
        print(f"Результат: {result['result'][:200]}...")
        
        # Тестируем HTTP
        print("\n🌐 Тест HTTP:")
        http_result = client.http("google.com", "EU", 2)
        print(f"HTTP успех: {http_result['success']}")
        
        if http_result['success']:
            print("✅ MCP HTTP работает!")
            print(f"HTTP результат: {http_result['result'][:200]}...")
        else:
            print(f"❌ HTTP ошибка: {http_result['error']}")
            
        # Тестируем locations
        print("\n📍 Тест locations:")
        loc_result = client.get_locations()
        print(f"Locations успех: {loc_result['success']}")
        
        if loc_result['success']:
            print("✅ MCP Locations работает!")
            print(f"Locations: {str(loc_result['result'])[:200]}...")
        else:
            print(f"❌ Locations ошибка: {loc_result['error']}")
    else:
        print(f"❌ MCP PING ошибка: {result['error']}")

def check_globalping_service():
    """Проверяет доступность сервиса Globalping"""
    
    print("\n🌐 Проверка сервиса Globalping...")
    print("=" * 50)
    
    # Проверяем основной сайт
    try:
        response = requests.get("https://globalping.io", timeout=5)
        print(f"Главный сайт: {response.status_code} ✅")
    except:
        print("Главный сайт: недоступен ❌")
    
    # Проверяем REST API
    try:
        response = requests.get("https://api.globalping.io/v1/credits", timeout=5)
        print(f"REST API: {response.status_code} ✅")
    except:
        print("REST API: недоступен ❌")
        
    # Проверяем MCP эндпоинт
    try:
        response = requests.get("https://mcp.globalping.dev", timeout=5)
        print(f"MCP эндпоинт: {response.status_code}")
        if response.status_code == 200:
            print("✅ MCP сервер доступен")
        elif response.status_code == 404:
            print("❌ MCP эндпоинт не найден")
        else:
            print(f"⚠️ MCP ответ: {response.status_code}")
    except Exception as e:
        print(f"❌ MCP недоступен: {str(e)}")

if __name__ == "__main__":
    print("🧪 Продвинутая диагностика Globalping MCP")
    print("=" * 60)
    
    try:
        # Проверяем сервис
        check_globalping_service()
        
        # Тестируем эндпоинты
        working_endpoints = test_mcp_endpoints()
        
        # Тестируем клиент
        test_improved_client()
        
        print("\n🏁 Диагностика завершена!")
        
        if working_endpoints:
            print("✅ Найдены рабочие MCP эндпоинты!")
        else:
            print("❌ MCP эндпоинты не работают")
            print("💡 Возможно, MCP сервер Globalping временно недоступен")
            print("🔄 Гибридный клиент автоматически переключится на REST API")
        
    except Exception as e:
        print(f"❌ Ошибка диагностики: {e}")
        import traceback
        traceback.print_exc() 