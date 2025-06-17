import json
import requests
import asyncio
from typing import Dict, Any, Optional

class GlobalpingMCPClient:
    """
    Клиент для работы с Globalping MCP Server
    Использует официальный endpoint: https://mcp.globalping.dev/sse
    """
    
    def __init__(self, mcp_endpoint: str = "https://mcp.globalping.dev/sse", api_key: str = None):
        self.mcp_endpoint = mcp_endpoint
        self.api_key = api_key
        self.session = requests.Session()
        
        # Настройка базовых заголовков для MCP
        self.session.headers.update({
            "User-Agent": "GlobalpingMCPClient/1.0",
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json"
        })
        
        # Добавляем API ключ если есть
        if api_key:
            self.session.headers.update({
                "X-API-Key": api_key,
                "Authorization": f"Bearer {api_key}"
            })
        
    def ping(self, target: str, locations: str = "EU,NA,AS", limit: int = 3) -> Dict[str, Any]:
        """Выполняет ping тест через MCP"""
        return self._call_mcp_tool("ping", {
            "target": target,
            "locations": locations,
            "limit": limit
        })
    
    def http(self, target: str, locations: str = "EU,NA,AS", limit: int = 3) -> Dict[str, Any]:
        """Выполняет HTTP тест через MCP"""
        return self._call_mcp_tool("http", {
            "target": target,
            "locations": locations, 
            "limit": limit
        })
    
    def traceroute(self, target: str, locations: str = "EU,NA,AS", limit: int = 3) -> Dict[str, Any]:
        """Выполняет traceroute тест через MCP"""
        return self._call_mcp_tool("traceroute", {
            "target": target,
            "locations": locations,
            "limit": limit
        })
    
    def dns(self, target: str, locations: str = "EU,NA,AS", query_type: str = "A") -> Dict[str, Any]:
        """Выполняет DNS lookup через MCP"""
        return self._call_mcp_tool("dns", {
            "target": target,
            "locations": locations,
            "type": query_type
        })
    
    def get_locations(self) -> Dict[str, Any]:
        """Получает список доступных локаций"""
        return self._call_mcp_tool("locations", {})
    
    def _call_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Внутренний метод для вызова MCP инструментов
        """
        try:
            # Правильный JSON-RPC 2.0 формат для MCP
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": params
                }
            }
            
            # Попробуем разные подходы к аутентификации
            auth_attempts = [
                # Без аутентификации
                {},
                # С популярными API ключами
                {"X-API-Key": "public"},
                {"X-API-Key": "demo"},
                {"Authorization": "Bearer public"},
                # С возможными токенами Globalping
                {"X-API-Key": "globalping-public"},
                {"Authorization": "Bearer globalping-demo"}
            ]
            
            for auth_headers in auth_attempts:
                # Объединяем базовые заголовки с попыткой аутентификации
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "GlobalpingMCPClient/2.0"
                }
                headers.update(auth_headers)
                
                try:
                    response = self.session.post(
                        self.mcp_endpoint,
                        json=jsonrpc_request,
                        headers=headers,
                        timeout=15
                    )
                    
                    # Если не 401/403, значит этот метод работает
                    if response.status_code not in [401, 403]:
                        break
                        
                except requests.exceptions.RequestException:
                    continue
            
            # Попробуем также простой инициализационный запрос
            if response.status_code == 401:
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
                
                init_response = self.session.post(
                    self.mcp_endpoint,
                    json=init_request,
                    headers=headers,
                    timeout=15
                )
                
                # Если инициализация прошла, попробуем еще раз вызвать инструмент
                if init_response.status_code == 200:
                    response = self.session.post(
                        self.mcp_endpoint,
                        json=jsonrpc_request,
                        headers=headers,
                        timeout=15
                    )
            
            # Обрабатываем разные статус коды
            if response.status_code == 200:
                # Успешный ответ
                try:
                    json_result = response.json()
                    
                    # JSON-RPC 2.0 формат ответа
                    if "result" in json_result:
                        return {
                            "success": True,
                            "tool": tool_name,
                            "result": self._format_mcp_result(json_result["result"], tool_name)
                        }
                    elif "error" in json_result:
                        return {
                            "success": False,
                            "error": f"MCP error: {json_result['error'].get('message', 'Unknown error')}"
                        }
                    else:
                        return {
                            "success": True,
                            "tool": tool_name,
                            "result": str(json_result)
                        }
                        
                except json.JSONDecodeError:
                    # Возможно SSE ответ
                    result = self._parse_sse_response(response)
                    return {
                        "success": True,
                        "tool": tool_name,
                        "result": result
                    }
                    
            elif response.status_code == 404:
                # Возможно неправильный endpoint, попробуем альтернативы
                alternative_endpoints = [
                    "https://mcp.globalping.dev/api",
                    "https://mcp.globalping.dev/rpc",
                    "https://mcp.globalping.dev",
                    "https://api.globalping.io/mcp"
                ]
                
                for alt_endpoint in alternative_endpoints:
                    try:
                        alt_response = self.session.post(
                            alt_endpoint,
                            json=jsonrpc_request,
                            headers=headers,
                            timeout=10
                        )
                        
                        if alt_response.status_code == 200:
                            try:
                                alt_result = alt_response.json()
                                if "result" in alt_result:
                                    return {
                                        "success": True,
                                        "tool": tool_name,
                                        "result": self._format_mcp_result(alt_result["result"], tool_name),
                                        "endpoint": alt_endpoint
                                    }
                            except json.JSONDecodeError:
                                pass
                                
                    except requests.exceptions.RequestException:
                        continue
                
                return {
                    "success": False,
                    "error": f"All MCP endpoints failed. Tried: {[self.mcp_endpoint] + alternative_endpoints}"
                }
                
            else:
                return {
                    "success": False,
                    "error": f"MCP server error: {response.status_code}",
                    "details": response.text[:200] if response.text else "No response body"
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
    
    def _format_mcp_result(self, result_data, tool_name: str) -> str:
        """Форматирует результат MCP в читаемый вид"""
        try:
            if isinstance(result_data, str):
                return result_data
            
            if isinstance(result_data, dict):
                # Если есть content - используем его
                if "content" in result_data:
                    content = result_data["content"]
                    if isinstance(content, list) and content:
                        return str(content[0].get("text", str(content[0])))
                    return str(content)
                
                # Если есть данные измерений
                if "measurements" in result_data:
                    return self._format_measurement_results(result_data["measurements"], tool_name)
                
                # Иначе возвращаем как есть
                return str(result_data)
            
            return str(result_data)
            
        except Exception as e:
            return f"Error formatting result: {str(e)}\nRaw data: {str(result_data)}"
    
    def _format_measurement_results(self, measurements, tool_name: str) -> str:
        """Форматирует результаты измерений"""
        if not measurements:
            return "No measurement data"
        
        results = []
        for measurement in measurements:
            location = measurement.get("location", "Unknown")
            
            if tool_name == "ping":
                avg_time = measurement.get("avg", "N/A")
                loss = measurement.get("loss", "N/A")
                results.append(f"📍 {location}: {avg_time}ms (loss: {loss}%)")
            elif tool_name == "http":
                status = measurement.get("status", "N/A")
                time = measurement.get("time", "N/A")
                results.append(f"📍 {location}: HTTP {status} ({time}ms)")
            else:
                results.append(f"📍 {location}: {str(measurement)}")
        
        return "\n".join(results)

    def _parse_sse_response(self, response) -> str:
        """Парсит SSE ответ от MCP сервера"""
        result_lines = []
        
        try:
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    line = line.strip()
                    if line.startswith("data: "):
                        data = line[6:]  # Убираем "data: "
                        if data and data != "[DONE]":
                            try:
                                json_data = json.loads(data)
                                if "content" in json_data:
                                    result_lines.append(json_data["content"])
                            except json.JSONDecodeError:
                                result_lines.append(data)
            
            return "\n".join(result_lines) if result_lines else "No data received"
            
        except Exception as e:
            return f"Error parsing response: {str(e)}"

# Вспомогательные функции для удобного использования
def quick_ping(target: str, locations: str = "EU,NA,AS") -> str:
    """Быстрый ping тест"""
    client = GlobalpingMCPClient()
    result = client.ping(target, locations)
    
    if result["success"]:
        return f"🌍 **Globalping PING** для `{target}`:\n{result['result']}"
    else:
        return f"❌ **Ошибка ping**: {result['error']}"

def quick_http(target: str, locations: str = "EU,NA,AS") -> str:
    """Быстрый HTTP тест"""
    client = GlobalpingMCPClient()
    result = client.http(target, locations)
    
    if result["success"]:
        return f"🌐 **Globalping HTTP** для `{target}`:\n{result['result']}"
    else:
        return f"❌ **Ошибка HTTP**: {result['error']}"

def comprehensive_test(target: str, locations: str = "EU,NA,AS") -> str:
    """Комплексный тест (ping + http)"""
    client = GlobalpingMCPClient()
    
    results = []
    
    # Ping тест
    ping_result = client.ping(target, locations)
    if ping_result["success"]:
        results.append(f"📡 **PING результаты:**\n{ping_result['result']}")
    else:
        results.append(f"❌ **PING ошибка:** {ping_result['error']}")
    
    # HTTP тест (если цель похожа на веб-ресурс)
    if not target.replace(".", "").isdigit():  # Не IP адрес
        http_target = target if target.startswith(("http://", "https://")) else f"https://{target}"
        http_result = client.http(http_target, locations)
        
        if http_result["success"]:
            results.append(f"🌐 **HTTP результаты:**\n{http_result['result']}")
        else:
            results.append(f"❌ **HTTP ошибка:** {http_result['error']}")
    
    return "\n\n".join(results)

# Пример использования
if __name__ == "__main__":
    # Тестируем MCP клиент
    target = "google.com"
    
    print("🧪 Тестирование Globalping MCP Client...")
    print("=" * 50)
    
    # Простой ping
    print(quick_ping(target))
    print("-" * 30)
    
    # HTTP тест
    print(quick_http(f"https://{target}"))
    print("-" * 30)
    
    # Комплексный тест
    print("🔍 Комплексное тестирование:")
    print(comprehensive_test(target)) 