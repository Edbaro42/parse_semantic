import requests
import xml.etree.ElementTree as ET
import json
import csv
from datetime import datetime
from collections import Counter
from pymorphy3 import MorphAnalyzer
from urllib.parse import urlparse
import time
import math
import re
import tkinter as tk


def show_completion_message():
    window = tk.Tk()
    window.title("Завершено")
    label = tk.Label(window, text="Сбор семантики завершен", padx=200, pady=30)
    label.pack()
    window.mainloop()

with open('keys.txt', 'r', encoding='utf-8') as file:
    # Читаем все строки из файла
    lines = file.readlines()

# Создаем словарь для хранения найденных значений
values = {}

# Определяем нужные ключи
keys = [
    'API_URL_YANDEX_SEARCH', 'API_URL_MUTAGEN', 'API_KEY_WORDKEEPER',
    'GEO_MUTAGEN', 'HAS_QUESTION', 'HAS_TOPONYM', 'MIN_POSITION', 'MIN_FREQ', 
    'FILTER_TYPE_QUESTION', 'FILTER_TYPE_TOPONYM', 'API_URL_YANDEX_SERP',
    'GEO_WORDKEEPER', 'FILTER_QUERIES'
]

# Обходим каждую строку и ищем нужные ключи
for line in lines:
    for key in keys:
        if line.startswith(key):
            # Находим значение после знака равно и удаляем пробелы
            value = line.split('==')[1].strip()
            # Сохраняем значение в словаре
            values[key] = value

# Присваиваем значения переменным
API_URL_YANDEX_SEARCH = values['API_URL_YANDEX_SEARCH']
API_URL_YANDEX_SERP = values['API_URL_YANDEX_SERP']
API_URL_MUTAGEN = values['API_URL_MUTAGEN']
API_KEY_WORDKEEPER = values['API_KEY_WORDKEEPER']
GEO_MUTAGEN = values['GEO_MUTAGEN']
HAS_QUESTION = int(values['HAS_QUESTION'])
HAS_TOPONYM = int(values['HAS_TOPONYM'])
MIN_POSITION = int(values['MIN_POSITION'])
GEO_WORDKEEPER = int(values['GEO_WORDKEEPER'])
MIN_FREQ = int(values['MIN_FREQ'])
FILTER_TYPE_QUESTION = values['FILTER_TYPE_QUESTION']
FILTER_TYPE_TOPONYM = values['FILTER_TYPE_TOPONYM']
FILTER_QUERIES = values['FILTER_QUERIES']

filename = 'results_{}.csv'.format(datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))
print(f"СОЗДАЕМ ФАЙЛ {filename}")

# Открываем CSV-файл для записи данных
with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)

    # Записываем заголовки столбцов в CSV
    writer.writerow(['phrase', 'keyword', 'region_wsqso'])

url_list = []

with open('ex_lemms.txt', 'r', encoding='utf-8') as ex_lemms_file:
    ex_lemms = ex_lemms_file.readlines()
ex_lemms = [ex_lemm.strip().lower() for ex_lemm in ex_lemms]

morph = MorphAnalyzer()

with open('h1.txt', 'r', encoding='utf-8') as file:
    phrases = file.readlines()

count = 0

for phrase in phrases:
    
    count = count + 1
   
    print(f"\n####################\n Начало итерации {count} \n####################")

    phrase = phrase.strip().lower() + " купить"
    pattern = r"(\d+)([xхна\*]+)(\d+)"
    replacement = r"\1 \3"
    re_results = re.sub(pattern, replacement, phrase)
    re_results = re.sub(r"\-|\/|\\|\|", r" ", re_results)
    re_results = re.sub(r"\"|\'|\(.+\)", r"", re_results)
    
    lemmas = set()

    for word in re_results.split():
        if word.lower() not in ex_lemms:
            lemma = morph.parse(word)[0].normal_form
            lemmas.add(lemma)
    
    api_url = API_URL_YANDEX_SEARCH + phrase
    response = requests.get(api_url)
    phrase_on_print = phrase.replace(" купить", "")
    print(f"Собираем SERP для заголовка h1: \"{phrase_on_print}\"")
    
    try:
        xml_data = ET.fromstring(response.text)
    except ET.ParseError:
        print(f"Ошибка при разборе XML для фразы: {phrase}")
        continue
    
    if 'error' in response.text:
        error_message = xml_data.find('.//error').text
        print(f"Ошибка при получении данных для фразы: {phrase}")
        print(f"Сообщение об ошибке: {error_message}")
        continue

    for doc in xml_data.findall('.//doc'):
        
        urls = doc.findall('.//url')
        for url in urls:
            url_text = url.text.lower()

            with open('exceptions.txt', 'r', encoding='utf-8') as exceptions_file:
                exceptions = exceptions_file.readlines()

            excluded = False
            for exception in exceptions:
                exception = exception.strip().lower()
                if exception in url_text:
                    excluded = True
                    break
        
            if not excluded:
                
                url_lemmas = set()
                hlwords = doc.findall('.//title/hlword') + doc.findall('.//headline/hlword')
                for hlword in hlwords:
                    hlword_text = hlword.text.lower()
                    hlword_lemma = morph.parse(hlword_text)[0].normal_form
                    url_lemmas.add(hlword_lemma)

                if "ozon.ru" in url_text:
                    url_list.append(url_text)
                elif all(word in url_lemmas for word in lemmas):  
                    def is_main_page(url):
                        parsed_url = urlparse(url)
                        path = parsed_url.path.strip('/')
                        return len(path) == 0
                    if not is_main_page(url_text):
                        url_list.append(url_text)
                        
                        print(f"  {url_text}")

    print(f"Собираем семантику с помощью https://mutagen.ru/ по урлам из SERP'а для h1: \"{phrase_on_print}\"...")
    # Открываем CSV-файл для записи данных
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        data_list = []  # Создаем список для хранения данных для каждого URL
        
        with open('minus_words.txt', 'r', encoding='utf-8') as minus_words_file:
            minus_words = minus_words_file.readlines()
            
        minus_words = [minus_word.strip().lower() for minus_word in minus_words]
        minus_words_list = ', '.join(minus_words)  # Соединяем все слова через запятую

        # Проходим по каждому URL и отправляем запросы на API
        for url in url_list:
            # Формируем тело запроса
            payload = {
                "region": GEO_MUTAGEN,
                "report": "report_keywords_organic",
                "page": url,
                "filter": [
                    {"column": "has_question", "filter_type": FILTER_TYPE_QUESTION, "val": HAS_QUESTION},
                    {"column": "has_toponym", "filter_type": FILTER_TYPE_TOPONYM, "val": HAS_TOPONYM},
                    {"column": "position", "filter_type": "less_or_eq", "val": MIN_POSITION},
                    {"column": "region_wsqso", "filter_type": "gr_or_eq", "val": MIN_FREQ},
                    {"column": "keyword", "filter_type": "not_like_any", "val": minus_words_list}
                ]
            }
            
            # Отправляем POST-запрос на API
            response = requests.post(API_URL_MUTAGEN, json=payload)
            time.sleep(2)

            data = response.json()

            if 'error' in response.text:
                error_message = data.get('error')
                continue
                
            for item in data:
                # Извлекаем нужные данные из объекта JSON
                keyword = item['keyword']

                # Добавляем данные в список и словарь
                data_list.append([phrase, keyword])
          
        print(f"Чистим семантику от мусора...")          
        # Удаление фраз, которые встречаются только один раз
        keyword_counts = Counter([item[1] for item in data_list])
        data_list = [item for item in data_list if keyword_counts[item[1]] > 1]

        # Удаление дублирующихся записей
        data_list = list(set(tuple(item) for item in data_list))
        
        # Удаление недописанных запросов
        with open('sps.txt', 'r', encoding='utf-8') as sps_file:
            sps_words = sps_file.read().splitlines()

        new_data_list = []
        for item in data_list:
            passage = item[1]
            words = passage.split()
            should_remove = False
            
            for word in sps_words:
                if words[0] == word or words[-1] == word:
                    should_remove = True
                    break
            
            if not should_remove:
                new_data_list.append(item)

        data_list = new_data_list 
            
        # Удаление слов без кириллицы, однословных несуществительных и существительных не им. падежа
        clear_data_list = []
        for item in data_list:
            phrase_clear = item[1]

            if re.match(FILTER_QUERIES, phrase_clear):
                continue

            word = phrase_clear.split()
            if len(word) == 1 and word[0] not in open('for_pymorphy.txt', 'r', encoding='utf-8').read():
                parsed_word = morph.parse(''.join(word))[0]
                if not (parsed_word.tag.POS == 'NOUN' and parsed_word.tag.case == 'nomn'):
                    continue
            clear_data_list.append(item)
            
        data_list = clear_data_list

        keywords_str = '\n'.join(['\"[{}]\"'.format(' '.join(['!{}'.format(word) for word in item[1].split()])) for item in data_list])

        print("Отправляем фразы в https://word-keeper.ru/ для сбора \"[!самой !точной !частотности]\"...")  
        # Проверяем, что есть хотя бы один keyword в data_list
        if not keywords_str:
            print("Нет ключевых слов для отправки запроса")
            print(f"Конец итерации {count}")
            continue

        # Разделяем строку на фразы по разделителю \n
        phrases = keywords_str.split("\n")
        
        # Разделяем фразы на пакеты по 1000 запросов
        num_chunks = math.ceil(len(phrases) / 1000)
        keywords_chunks = [phrases[i*1000:(i+1)*1000] for i in range(num_chunks)]

        for chunk in keywords_chunks:
            # Создаем тело запроса
            payload = {
                "text": "\n".join(chunk),
                "token": API_KEY_WORDKEEPER,
                "geo": GEO_WORDKEEPER
            }

            # Отправляем POST-запрос на API
            response = requests.post('https://word-keeper.ru/api/create_freqDiff', json=payload)

            if 'id' in response.json():
                result_id = response.json()['id']
                time.sleep(10)
                print("Ждем ответа от word-keeper.ru...")

                while True:
                    # Создаем тело запроса
                    payload = {
                        "token": API_KEY_WORDKEEPER,
                        "id": result_id
                    }

                    # Отправляем POST-запрос на API
                    response = requests.post('https://word-keeper.ru/api/get_result', json=payload)

                    if response.status_code != 200 or response.json()['status'] == "error" or response.json()['results'] is None:
                        print(f"Word-Keeper вернул ошибку при попытке получения результата: {response.status_code}|{response.json()['status']} (частотности не получены)")
                        break
                    elif response.json()['status'] == "work":
                        time.sleep(10)
                        print("...продолжаем ждать ответа от word-keeper.ru...")
                    else:
                        results = response.json()['results']
                        break                    
                
                for keyword, region_wsqso in list(results.items()):
                    if int(region_wsqso) < 3:
                        del results[keyword]
                data_list = []
                for keyword, region_wsqso in list(results.items()):
                    keyword = re.sub(r'["\'!\[\]]', '', keyword)
                    phrase = phrase.replace(" купить", "")
                    data_list.append([phrase, keyword, region_wsqso])
                    
                data_list = sorted(data_list, key=lambda x: int(x[2]), reverse=True)
                
                # Создаем тело запроса
                payload = {
                    "token": API_KEY_WORDKEEPER,
                    "id": result_id
                }

                # Отправляем POST-запрос на API
                response = requests.post('https://word-keeper.ru/api/remove', json=payload)
                
            else:
                print(f"Word-Keeper вернул ошибку при попытке отправить задачу: {response.status_code}|{response.json()['status']} (частотности не получены)")

        print(f"Записываем семантику и ее частотку для h1 \"{phrase_on_print}\" в csv...")               
        # Записываем данные из списка в CSV файл
        writer.writerows(data_list)     

    url_list = []

show_completion_message()
