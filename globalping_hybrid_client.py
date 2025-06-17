import json
import requests
import time
from typing import Dict, Any, Optional

class GlobalpingHybridClient:
    """
    Гибридный клиент для Globalping:
    1. Сначала пытается использовать MCP Server
    2. При неудаче переключается на прямой REST API
    """
    
    def __init__(self, prefer_mcp: bool = True):
        self.prefer_mcp = prefer_mcp
        self.mcp_endpoint = "https://mcp.globalping.dev/sse"
        self.rest_api_base = "https://api.globalping.io/v1"
        self.session = requests.Session()
        
    def ping(self, target: str, locations: str = "EU", limit: int = 2) -> Dict[str, Any]:
        """Выполняет ping тест"""
        if self.prefer_mcp:
            result = self._try_mcp_test(target, "ping", locations, limit)
            if result["success"]:
                return result
            # Fallback к REST API
            print("⚠️ MCP не работает, переключаюсь на REST API...")
        
        return self._rest_api_ping(target, locations, limit)
    
    def http(self, target: str, locations: str = "EU", limit: int = 2) -> Dict[str, Any]:
        """Выполняет HTTP тест"""
        if self.prefer_mcp:
            result = self._try_mcp_test(target, "http", locations, limit)
            if result["success"]:
                return result
            print("⚠️ MCP не работает, переключаюсь на REST API...")
        
        return self._rest_api_http(target, locations, limit)
    
    def traceroute(self, target: str, locations: str = "EU,NA,AS", limit: int = 3) -> Dict[str, Any]:
        """Выполняет traceroute тест"""
        if self.prefer_mcp:
            result = self._try_mcp_traceroute(target, locations, limit)
            if result["success"]:
                return result
            print("⚠️ MCP не работает, переключаюсь на REST API...")
        
        return self._rest_api_traceroute(target, locations, limit)
    
    def _try_mcp_test(self, target: str, test_type: str, locations: str, limit: int) -> Dict[str, Any]:
        """Пытается выполнить тест через MCP"""
        try:
            # Пробуем разные форматы MCP запроса
            formats = [
                # Формат 1: Простой
                {
                    "tool": test_type,
                    "target": target,
                    "locations": locations,
                    "limit": limit
                },
                # Формат 2: JSON-RPC
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": test_type,
                        "arguments": {
                            "target": target,
                            "locations": locations,
                            "limit": limit
                        }
                    }
                }
            ]
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "GlobalpingHybridClient/1.0"
            }
            
            for i, request_format in enumerate(formats):
                try:
                    response = self.session.post(
                        self.mcp_endpoint,
                        json=request_format,
                        headers=headers,
                        timeout=15
                    )
                    
                    if response.status_code == 200:
                        # Успешный ответ
                        try:
                            result_data = response.json()
                            formatted_result = self._format_mcp_result(result_data, test_type, target)
                            return {
                                "success": True,
                                "source": f"MCP (format {i+1})",
                                "result": formatted_result
                            }
                        except json.JSONDecodeError:
                            return {
                                "success": True,
                                "source": f"MCP (format {i+1})",
                                "result": response.text
                            }
                    
                except requests.exceptions.RequestException:
                    continue
            
            return {"success": False, "error": "All MCP formats failed"}
            
        except Exception as e:
            return {"success": False, "error": f"MCP error: {str(e)}"}
    
    def _try_mcp_traceroute(self, target: str, locations: str, limit: int) -> Dict[str, Any]:
        """Пытается выполнить traceroute через MCP"""
        # Аналогично ping, но с инструментом "traceroute"  
        return self._try_mcp_test(target.replace("ping", "traceroute"), "traceroute", locations, limit)
    
    def _format_mcp_result(self, data: Dict, test_type: str, target: str) -> str:
        """Форматирует результат MCP в читаемый вид"""
        try:
            if isinstance(data, str):
                return data
            
            # Пробуем извлечь полезную информацию
            if "result" in data:
                return str(data["result"])
            elif "content" in data:
                return str(data["content"])
            else:
                return str(data)
                
        except Exception:
            return str(data)
    
    def _rest_api_ping(self, target: str, locations: str, limit: int) -> Dict[str, Any]:
        """Выполняет ping через прямой REST API"""
        return self._execute_rest_test(target, "ping", locations)
    
    def _rest_api_http(self, target: str, locations: str, limit: int) -> Dict[str, Any]:
        """Выполняет HTTP тест через прямой REST API"""
        # Убираем обработку URL здесь, она будет в _execute_rest_test
        return self._execute_rest_test(target, "http", locations)
    
    def _rest_api_traceroute(self, target: str, locations: str, limit: int) -> Dict[str, Any]:
        """Выполняет traceroute через прямой REST API"""
        clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
        return self._execute_rest_test(clean_target, "traceroute", locations)
    
    def _execute_rest_test(self, target: str, test_type: str, locations: str) -> Dict[str, Any]:
        """Выполняет тест через Globalping REST API"""
        try:
            # Создаем измерение
            create_url = f"{self.rest_api_base}/measurements"
            
            # Правильный формат для разных типов тестов
            payload = {
                "type": test_type,
                "target": target,
                "locations": [{"magic": locations}]
            }
            
            # Добавляем опции только если нужно
            if test_type == "ping":
                payload["measurementOptions"] = {"packets": 3}
            elif test_type == "traceroute":
                payload["measurementOptions"] = {"protocol": "ICMP"}
            
            # Специальная обработка для HTTP
            if test_type == "http":
                # Для HTTP тестов Globalping принимает ТОЛЬКО доменные имена без протокола
                if target.startswith(("http://", "https://")):
                    # Убираем протокол и путь, оставляем только домен
                    clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
                    payload["target"] = clean_target
                else:
                    payload["target"] = target
            
            headers = {"Content-Type": "application/json"}
            response = self.session.post(create_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code != 202:
                return {
                    "success": False,
                    "error": f"Failed to create measurement: {response.status_code}",
                    "details": response.text
                }
                
            measurement_data = response.json()
            measurement_id = measurement_data.get("id")
            
            if not measurement_id:
                return {
                    "success": False,
                    "error": "No measurement ID received"
                }
            
            # Ждем результаты
            for attempt in range(20):  # 20 секунд максимум
                result_url = f"{self.rest_api_base}/measurements/{measurement_id}"
                result_response = self.session.get(result_url, timeout=10)
                
                if result_response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Failed to get results: {result_response.status_code}"
                    }
                    
                result_data = result_response.json()
                
                if result_data.get("status") == "finished":
                    formatted_result = self._format_rest_results(result_data, test_type, target)
                    return {
                        "success": True,
                        "source": "REST API",
                        "result": formatted_result
                    }
                    
                elif result_data.get("status") == "failed":
                    return {
                        "success": False,
                        "error": f"Test failed: {result_data.get('error', 'Unknown error')}"
                    }
                    
                time.sleep(1)
                
            return {
                "success": False,
                "error": "Timeout waiting for results"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def _format_rest_results(self, result_data: Dict, test_type: str, target: str) -> str:
        """Форматирует результаты REST API в читаемый вид"""
        results = []
        
        for result in result_data.get("results", []):
            probe = result.get("probe", {})
            location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
            
            if test_type == "ping":
                stats = result.get("result", {}).get("stats", {})
                avg_time = stats.get("avg", "N/A")
                packet_loss = stats.get("loss", "N/A")
                results.append(f"📍 {location}: {avg_time}ms (loss: {packet_loss}%)")
                
            elif test_type == "http":
                http_result = result.get("result", {})
                status = http_result.get("status", "N/A")
                total_time = http_result.get("timings", {}).get("total", "N/A")
                results.append(f"📍 {location}: HTTP {status} ({total_time}ms)")
                
            elif test_type == "traceroute":
                hops = result.get("result", {}).get("hops", [])
                hop_count = len(hops)
                last_hop = hops[-1] if hops else {}
                last_time = last_hop.get("timings", [{}])[-1].get("rtt", "N/A") if last_hop.get("timings") else "N/A"
                results.append(f"📍 {location}: {hop_count} hops, last hop: {last_time}ms")
        
        return f"🌍 **Globalping {test_type.upper()}** для `{target}`:\n" + "\n".join(results)

# Удобные функции
def hybrid_ping(target: str, locations: str = "EU") -> str:
    """Быстрый ping тест с автоматическим fallback"""
    client = GlobalpingHybridClient()
    result = client.ping(target, locations)
    
    if result["success"]:
        return f"✅ Источник: {result.get('source', 'Unknown')}\n{result['result']}"
    else:
        return f"❌ **Ошибка**: {result['error']}"

def hybrid_http(target: str, locations: str = "EU") -> str:
    """Быстрый HTTP тест с автоматическим fallback"""
    client = GlobalpingHybridClient()
    result = client.http(target, locations)
    
    if result["success"]:
        return f"✅ Источник: {result.get('source', 'Unknown')}\n{result['result']}"
    else:
        return f"❌ **Ошибка**: {result['error']}"

def comprehensive_hybrid_test(target: str, locations: str = "EU,NA,AS") -> str:
    """Комплексный тест с fallback"""
    client = GlobalpingHybridClient()
    
    results = []
    
    # Ping тест
    ping_result = client.ping(target, locations)
    if ping_result["success"]:
        results.append(f"📡 **PING** (via {ping_result.get('source', 'Unknown')}):\n{ping_result['result']}")
    else:
        results.append(f"❌ **PING ошибка**: {ping_result['error']}")
    
    # HTTP тест (если не IP)
    if not target.replace(".", "").isdigit():
        http_result = client.http(target, locations)
        if http_result["success"]:
            results.append(f"🌐 **HTTP** (via {http_result.get('source', 'Unknown')}):\n{http_result['result']}")
        else:
            results.append(f"❌ **HTTP ошибка**: {http_result['error']}")
    
    return "\n\n".join(results)

# Тестирование
if __name__ == "__main__":
    print("🧪 Тестирование гибридного Globalping клиента...")
    print("=" * 60)
    
    target = "google.com"
    
    # Тест 1: Ping
    print("📡 Ping тест:")
    print(hybrid_ping(target))
    print("-" * 40)
    
    # Тест 2: HTTP
    print("🌐 HTTP тест:")
    print(hybrid_http(target))
    print("-" * 40)
    
    # Тест 3: Комплексный
    print("🔍 Комплексный тест:")
    print(comprehensive_hybrid_test(target)) 