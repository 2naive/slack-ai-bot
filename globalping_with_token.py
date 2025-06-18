import json
import requests
import time
from typing import Dict, Any

class GlobalpingTokenClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.rest_api_base = "https://api.globalping.io/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        })
        
    def ping(self, target: str, locations: str = "EU", limit: int = 2) -> Dict[str, Any]:
        return self._execute_test(target, "ping", locations, limit)
    
    def http(self, target: str, locations: str = "EU", limit: int = 2) -> Dict[str, Any]:
        return self._execute_test(target, "http", locations, limit)
    
    def dns(self, target: str, locations: str = "EU", limit: int = 2) -> Dict[str, Any]:
        return self._execute_test(target, "dns", locations, limit)
    
    def traceroute(self, target: str, locations: str = "EU", limit: int = 2) -> Dict[str, Any]:
        return self._execute_test(target, "traceroute", locations, limit)
    
    def mtr(self, target: str, locations: str = "EU", limit: int = 2) -> Dict[str, Any]:
        return self._execute_test(target, "mtr", locations, limit)
    
    def _execute_test(self, target: str, test_type: str, locations: str, limit: int = 2) -> Dict[str, Any]:
        try:
            # Очищаем URL от протокола для всех типов тестов
            clean_target = target
            if target.startswith(("http://", "https://")):
                clean_target = target.replace("https://", "").replace("http://", "").split("/")[0]
            
            # Правильно формируем локации - разбиваем строку на отдельные magic объекты
            location_objects = []
            for loc in locations.split(","):
                location_objects.append({"magic": loc.strip()})
            
            payload = {
                "type": test_type,
                "target": clean_target,
                "locations": location_objects,
                "limit": limit
            }
            
            if test_type == "ping":
                payload["measurementOptions"] = {"packets": 3}
            elif test_type == "dns":
                payload["measurementOptions"] = {"query": {"type": "A"}}
            
            response = self.session.post(f"{self.rest_api_base}/measurements", json=payload, timeout=10)
            
            if response.status_code != 202:
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
            measurement_id = response.json().get("id")
            if not measurement_id:
                return {"success": False, "error": "No measurement ID"}
            
            # Ждем результаты
            for attempt in range(20):
                result_response = self.session.get(f"{self.rest_api_base}/measurements/{measurement_id}", timeout=10)
                
                if result_response.status_code == 200:
                    result_data = result_response.json()
                    
                    if result_data.get("status") == "finished":
                        formatted_result = self._format_results(result_data, test_type, clean_target)
                        return {"success": True, "source": "REST API + Token", "result": formatted_result}
                    elif result_data.get("status") == "failed":
                        return {"success": False, "error": f"Test failed: {result_data.get('error', 'Unknown error')}"}
                        
                time.sleep(1)
                
            return {"success": False, "error": "Timeout"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _format_results(self, result_data: Dict, test_type: str, target: str) -> str:
        results = []
        
        for result in result_data.get("results", []):
            probe = result.get("probe", {})
            location = f"{probe.get('city', 'Unknown')}, {probe.get('country', 'Unknown')}"
            
            if test_type == "ping":
                stats = result.get("result", {}).get("stats", {})
                avg_time = stats.get("avg", "N/A")
                packet_loss = stats.get("loss", "N/A")
                results.append(f"📍 {location}: {avg_time}ms (потерь: {packet_loss}%)")
            elif test_type == "http":
                http_result = result.get("result", {})
                status = http_result.get("status", "N/A")
                total_time = http_result.get("timings", {}).get("total", "N/A")
                results.append(f"📍 {location}: HTTP {status} ({total_time}ms)")
            elif test_type == "dns":
                dns_result = result.get("result", {})
                answers = dns_result.get("answers", [])
                if answers:
                    ip = answers[0].get("value", "N/A")
                    results.append(f"📍 {location}: {ip}")
                else:
                    results.append(f"📍 {location}: No DNS response")
            elif test_type == "traceroute":
                trace_result = result.get("result", {})
                hops = trace_result.get("hops", [])
                if hops:
                    hop_details = []
                    for hop_index, hop in enumerate(hops, 1):
                        hop_num = hop_index  # Используем индекс как номер хопа
                        timings = hop.get("timings", [])
                        
                        if timings:
                            # Берем первый успешный timing
                            timing = timings[0]
                            rtt = timing.get("rtt", "N/A")
                            
                            # Получаем IP или hostname из правильных полей
                            ip_or_host = hop.get("resolvedHostname") or hop.get("resolvedAddress") or "* * *"
                            
                            hop_details.append(f"  {hop_num:2}. {ip_or_host} - {rtt}ms")
                        else:
                            hop_details.append(f"  {hop_num:2}. * * * (timeout)")
                    
                    results.append(f"📍 {location} TRACEROUTE:\n" + "\n".join(hop_details))
                else:
                    results.append(f"📍 {location}: Traceroute данные недоступны")
            elif test_type == "mtr":
                mtr_result = result.get("result", {})
                hops = mtr_result.get("hops", [])
                    
                if hops:
                    hop_details = []
                    for hop_index, hop in enumerate(hops, 1):
                        hop_num = hop_index  # Используем индекс как номер хопа
                        stats = hop.get("stats", {})
                        avg_time = stats.get("avg", "N/A")
                        packet_loss = stats.get("loss", 0)
                        
                        # Получаем IP или hostname из правильных полей
                        ip_or_host = hop.get("resolvedHostname") or hop.get("resolvedAddress") or "* * *"
                        
                        # Форматируем строку хопа
                        loss_str = f" ({packet_loss}% loss)" if packet_loss > 0 else ""
                        hop_details.append(f"  {hop_num:2}. {ip_or_host} - {avg_time}ms{loss_str}")
                    
                    results.append(f"📍 {location} MTR:\n" + "\n".join(hop_details))
                else:
                    results.append(f"📍 {location}: MTR данные недоступны")
        
        return f"🌍 *{test_type.upper()}* для `{target}`:\n" + "\n".join(results)

    def get_credits(self) -> Dict[str, Any]:
        try:
            response = self.session.get(f"{self.rest_api_base}/credits")
            if response.status_code == 200:
                return {"success": True, "credits": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

def token_ping(api_token: str, target: str, locations: str = "EU") -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.ping(target, locations)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка ping**: {result['error']}"

def token_http(api_token: str, target: str, locations: str = "EU") -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.http(target, locations)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка http**: {result['error']}"

def token_dns(api_token: str, target: str, locations: str = "EU") -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.dns(target, locations)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка dns**: {result['error']}"

def token_traceroute(api_token: str, target: str, locations: str = "EU") -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.traceroute(target, locations)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка traceroute**: {result['error']}"

def token_mtr(api_token: str, target: str, locations: str = "EU") -> str:
    client = GlobalpingTokenClient(api_token)
    result = client.mtr(target, locations)
    if result["success"]:
        return f"✅ {result['result']}"
    else:
        return f"❌ **Ошибка mtr**: {result['error']}"

def comprehensive_token_test(api_token: str, target: str, locations: str = "EU,NA") -> str:
    client = GlobalpingTokenClient(api_token)
    results = []
    
    # Проверяем кредиты
    credits = client.get_credits()
    if credits["success"]:
        remaining = credits["credits"].get("remaining", "N/A")
        results.append(f"💰 **Кредиты**: {remaining}")
    
    # Ping тест
    ping_result = client.ping(target, locations, limit=2)
    if ping_result["success"]:
        results.append(f"📡 **PING**:\n{ping_result['result']}")
    else:
        results.append(f"❌ **PING ошибка**: {ping_result['error']}")
    
    # HTTP тест (если не IP)
    if not target.replace(".", "").replace(":", "").isdigit():
        http_result = client.http(target, locations, limit=2)
        if http_result["success"]:
            results.append(f"🌐 **HTTP**:\n{http_result['result']}")
        else:
            results.append(f"❌ **HTTP ошибка**: {http_result['error']}")
    
    return "\n" + "="*60 + "\n" + "\n\n".join(results) 