#!/usr/bin/env python3
"""
Тестовая программа для исправленного Globalping MCP клиента
"""

from globalping_mcp_client import GlobalpingMCPClient
import requests
import json

def test_endpoints():
    """Тестирует разные MCP эндпоинты"""
    
    print("🔍 Тестирование MCP эндпоинтов...")
    print("=" * 50)
    
    endpoints = [
        "https://mcp.globalping.dev/sse",
        "https://mcp.globalping.dev/api",
        "https://mcp.globalping.dev/rpc",
        "https://mcp.globalping.dev",
        "https://api.globalping.io/mcp"
    ]
    
    test_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }
    
    for endpoint in endpoints:
        print(f"\n🎯 Тестирование: {endpoint}")
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GlobalpingMCPClient/2.0"
        }
        
        try:
            response = requests.post(
                endpoint,
                json=test_request,
                headers=headers,
                timeout=10
            )
            
            print(f"Статус: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print("✅ Успешный ответ!")
                    print(f"Данные: {json.dumps(result, indent=2)[:200]}...")
                except json.JSONDecodeError:
                    print("✅ Ответ получен, но не JSON")
                    print(f"Содержимое: {response.text[:200]}...")
                    
            elif response.status_code == 401:
                print("❌ 401 - Требуется аутентификация")
                
            elif response.status_code == 404:
                print("❌ 404 - Эндпоинт не найден")
                
            else:
                print(f"❌ {response.status_code} - {response.text[:100]}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка сети: {str(e)}")
        
        print("-" * 30)

def test_mcp_initialize():
    """Тестирует инициализацию MCP"""
    
    print("\n🚀 Тестирование инициализации MCP...")
    print("=" * 50)
    
    init_request = {
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
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "GlobalpingMCPClient/2.0"
    }
    
    try:
        response = requests.post(
            "https://mcp.globalping.dev/sse",
            json=init_request,
            headers=headers,
            timeout=10
        )
        
        print(f"Статус инициализации: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("✅ Инициализация успешна!")
                print(f"Capabilities: {result.get('result', {}).get('capabilities', {})}")
                return True
            except json.JSONDecodeError:
                print("✅ Инициализация прошла, но ответ не JSON")
                return True
        else:
            print(f"❌ Ошибка инициализации: {response.text[:200]}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка сети при инициализации: {str(e)}")
        return False

def test_fixed_mcp_client():
    """Тестирует исправленный MCP клиент"""
    
    print("\n🔧 Тестирование исправленного MCP клиента...")
    print("=" * 50)
    
    # Тестируем с разными конфигурациями
    test_configs = [
        {"api_key": None, "name": "Без аутентификации"},
        {"api_key": "public", "name": "С публичным ключом"},
        {"api_key": "demo", "name": "С демо ключом"},
    ]
    
    for config in test_configs:
        print(f"\n📋 {config['name']}:")
        
        client = GlobalpingMCPClient(api_key=config["api_key"])
        
        # Тест ping
        result = client.ping("google.com", "EU")
        print(f"Ping результат: {result['success']}")
        
        if result['success']:
            print("✅ MCP работает!")
            print(f"Результат: {result['result'][:150]}...")
            
            # Если ping работает, попробуем HTTP
            http_result = client.http("google.com", "EU")
            print(f"HTTP результат: {http_result['success']}")
            if http_result['success']:
                print(f"HTTP данные: {http_result['result'][:150]}...")
            else:
                print(f"HTTP ошибка: {http_result['error']}")
            break
        else:
            print(f"❌ Ошибка: {result['error']}")
    
    print("\n" + "="*50)

def test_alternative_methods():
    """Тестирует альтернативные методы подключения к MCP"""
    
    print("\n🔄 Тестирование альтернативных методов...")
    print("=" * 50)
    
    # Тестируем GET запрос (возможно для SSE)
    try:
        response = requests.get(
            "https://mcp.globalping.dev/sse",
            headers={
                "Accept": "text/event-stream",
                "User-Agent": "GlobalpingMCPClient/2.0"
            },
            timeout=5
        )
        
        print(f"GET запрос: {response.status_code}")
        if response.status_code == 200:
            print("✅ SSE эндпоинт доступен!")
            print(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ GET запрос неудачен: {str(e)}")
    
    # Тестируем проверку доступности сервиса
    try:
        response = requests.get("https://globalping.io", timeout=5)
        print(f"Главный сайт Globalping: {response.status_code}")
        if response.status_code == 200:
            print("✅ Globalping сервис доступен")
    except requests.exceptions.RequestException as e:
        print(f"❌ Главный сайт недоступен: {str(e)}")

if __name__ == "__main__":
    print("🧪 Диагностика исправленного Globalping MCP")
    print("=" * 60)
    
    try:
        # Тестируем endpoints
        test_endpoints()
        
        # Тестируем инициализацию
        init_success = test_mcp_initialize()
        
        # Тестируем клиент
        test_fixed_mcp_client()
        
        # Альтернативные методы
        test_alternative_methods()
        
        print("\n✅ Диагностика завершена!")
        print("\n💡 Результаты покажут, работает ли MCP сервер")
        print("Если все еще не работает - проблема на стороне сервера Globalping")
        
    except Exception as e:
        print(f"❌ Ошибка диагностики: {e}")
        import traceback
        traceback.print_exc() 