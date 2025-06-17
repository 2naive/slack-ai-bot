#!/usr/bin/env python3
"""
Быстрый тест основных функций Slack бота
"""

# Импортируем функции из бота без запуска Slack
import sys
import os

# Добавляем путь к модулям
sys.path.append(os.path.dirname(__file__))

from slack_ai_bot import globalping_hybrid_check, extract_targets, run_command

def test_target_extraction():
    """Тестирует извлечение целей из сообщений"""
    print("🔍 Тестирование извлечения целей из сообщений")
    print("-" * 40)
    
    test_messages = [
        {
            'text': 'google.com не работает',
            'expected': ['google.com']
        },
        {
            'text': 'Проверьте https://github.com',
            'expected': ['https://github.com']
        },
        {
            'text': 'Сайт 8.8.8.8 недоступен',
            'expected': ['8.8.8.8']
        },
        {
            'text': 'Проблемы с example.org и test.com',
            'expected': ['example.org', 'test.com']
        }
    ]
    
    for test_case in test_messages:
        event = {'text': test_case['text']}
        targets = extract_targets(event)
        print(f"Текст: '{test_case['text']}'")
        print(f"Найдено: {targets}")
        print(f"Ожидалось: {test_case['expected']}")
        print(f"Результат: {'✅' if targets == test_case['expected'] else '❌'}")
        print()

def test_hybrid_globalping():
    """Тестирует гибридную интеграцию Globalping"""
    print("🌍 Тестирование гибридной Globalping интеграции")
    print("-" * 40)
    
    test_cases = [
        {'target': 'google.com', 'test_type': 'ping'},
        {'target': 'github.com', 'test_type': 'http'}
    ]
    
    for test_case in test_cases:
        print(f"Тестирование {test_case['test_type']} для {test_case['target']}...")
        result = globalping_hybrid_check(
            test_case['target'], 
            test_type=test_case['test_type'],
            locations="EU"
        )
        print(f"Результат: {result[:150]}...")
        print()

def test_local_commands():
    """Тестирует локальные сетевые команды"""
    print("💻 Тестирование локальных команд")
    print("-" * 40)
    
    commands = [
        'ping -n 2 google.com',
        'nslookup google.com'
    ]
    
    for command in commands:
        print(f"Команда: {command}")
        result = run_command(command)
        print(f"Результат: {result[:100]}...")
        print()

if __name__ == "__main__":
    print("🧪 Быстрый тест Slack AI Bot функций")
    print("=" * 50)
    
    try:
        test_target_extraction()
        test_hybrid_globalping()
        test_local_commands()
        
        print("✅ Все тесты завершены!")
        print("\n🚀 Готово к запуску:")
        print("python slack_ai_bot.py")
        
    except ImportError as e:
        print(f"❌ Ошибка импорта: {e}")
        print("Проверьте, что все файлы находятся в правильных местах")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        print("Убедитесь в корректности зависимостей") 