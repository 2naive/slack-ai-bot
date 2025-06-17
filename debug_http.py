#!/usr/bin/env python3
"""
Отладочный скрипт для тестирования HTTP запросов к Globalping REST API
"""

import requests
import json
import time

def test_http_request():
    """Тестирует HTTP запрос к Globalping"""
    
    # Тестируем разные форматы HTTP запросов
    test_cases = [
        {
            "name": "Простой HTTP",
            "payload": {
                "type": "http",
                "target": "https://google.com",
                "locations": [{"magic": "EU"}]
            }
        },
        {
            "name": "HTTP без протокола",
            "payload": {
                "type": "http", 
                "target": "google.com",
                "locations": [{"magic": "EU"}]
            }
        },
        {
            "name": "Ping для сравнения",
            "payload": {
                "type": "ping",
                "target": "google.com",
                "locations": [{"magic": "EU"}],
                "measurementOptions": {"packets": 3}
            }
        }
    ]
    
    base_url = "https://api.globalping.io/v1/measurements"
    headers = {"Content-Type": "application/json"}
    
    for test_case in test_cases:
        print(f"\n🧪 Тестирование: {test_case['name']}")
        print(f"Payload: {json.dumps(test_case['payload'], indent=2)}")
        
        try:
            response = requests.post(
                base_url,
                json=test_case['payload'],
                headers=headers,
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 202:
                print("✅ Запрос принят!")
                
                # Пробуем получить результат
                data = response.json()
                measurement_id = data.get("id")
                print(f"Measurement ID: {measurement_id}")
                
                if measurement_id:
                    # Ждем результат
                    for attempt in range(10):
                        result_url = f"https://api.globalping.io/v1/measurements/{measurement_id}"
                        result_response = requests.get(result_url, timeout=10)
                        
                        if result_response.status_code == 200:
                            result_data = result_response.json()
                            status = result_data.get("status")
                            print(f"Статус: {status}")
                            
                            if status == "finished":
                                print("✅ Тест завершен успешно!")
                                results = result_data.get("results", [])
                                for result in results[:2]:  # Показываем первые 2 результата
                                    probe = result.get("probe", {})
                                    location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
                                    print(f"  📍 {location}")
                                break
                            elif status == "failed":
                                print(f"❌ Тест неудачен: {result_data.get('error', 'Unknown')}")
                                break
                        
                        time.sleep(1)
                    
            else:
                print(f"❌ Ошибка: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Детали ошибки: {json.dumps(error_data, indent=2)}")
                except:
                    print(f"Текст ошибки: {response.text}")
                    
        except Exception as e:
            print(f"❌ Исключение: {str(e)}")
        
        print("-" * 50)

if __name__ == "__main__":
    print("🔍 Отладка HTTP запросов к Globalping REST API")
    print("=" * 60)
    
    test_http_request()
    
    print("\n✅ Отладка завершена!") 