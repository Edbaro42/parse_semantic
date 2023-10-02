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

API_URL_YANDEX_SEARCH = ""
API_URL_MUTAGEN = ""
API_KEY_WORDKEEPER = ""

filename = 'results_{}.csv'.format(datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))

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

for phrase in phrases:
    phrase = phrase.strip().lower() + " купить"

    lemmas = set()

    for word in phrase.split():
        if word.lower() not in ex_lemms:
            lemma = morph.parse(word)[0].normal_form
            lemmas.add(lemma)
    
    api_url = API_URL_YANDEX_SEARCH + phrase
    response = requests.get(api_url)
    
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

    # Открываем CSV-файл для записи данных
    with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        data_list = []  # Создаем список для хранения данных для каждого URL
        
        with open('minus_words.txt', 'r', encoding='utf-8') as minus_words_file:
            minus_words = minus_words_file.readlines()
            
        minus_words = [minus_word.strip().lower() for minus_word in minus_words]  # Удаляем лишние пробелы и символы новой строки
        minus_words_list = ', '.join(minus_words)  # Соединяем все слова через запятую

        # Проходим по каждому URL и отправляем запросы на API
        for url in url_list:
            # Формируем тело запроса
            payload = {
                "region": "yandex_msk",
                "report": "report_keywords_organic",
                "page": url,
                "filter": [
                    {"column": "has_question", "filter_type": "eq", "val": 0},
                    {"column": "has_toponym", "filter_type": "eq", "val": 0},
                    {"column": "position", "filter_type": "less", "val": 11},
                    {"column": "region_wsqso", "filter_type": "gr_or_eq", "val": 0},
                    {"column": "keyword", "filter_type": "not_like_any",
                     "val": minus_words_list}
                ]
            }
			
            # Отправляем POST-запрос на API
            response = requests.post(API_URL_MUTAGEN, json=payload)

            data = response.json()

            if 'error' in response.text:
                error_message = data.get('error')
                continue
                
            for item in data:
                # Извлекаем нужные данные из объекта JSON
                keyword = item['keyword']

                # Добавляем данные в список и словарь
                data_list.append([phrase, keyword])
                    
        # Удаление фраз, которые встречаются только один раз
        keyword_counts = Counter([item[1] for item in data_list])
        data_list = [item for item in data_list if keyword_counts[item[1]] > 1]

        # Удаление дублирующихся записей
        data_list = list(set(tuple(item) for item in data_list))
        
        keywords_str = '\n'.join(['\"[{}]\"'.format(' '.join(['!{}'.format(word) for word in item[1].split()])) for item in data_list])

        # Проверяем, что есть хотя бы один keyword в data_list
        if not keywords_str:
            print("Нет ключевых слов для отправки запроса")
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
                "geo": 1
            }

            # Отправляем POST-запрос на API
            response = requests.post('https://word-keeper.ru/api/create_freqDiff', json=payload)

            if 'id' in response.json():
                result_id = response.json()['id']
                time.sleep(10)

                while True:
                    # Создаем тело запроса
                    payload = {
                        "token": API_KEY_WORDKEEPER,
                        "id": result_id
                    }

                    # Отправляем POST-запрос на API
                    response = requests.post('https://word-keeper.ru/api/get_result', json=payload)

                    if 'status' in response.json() and response.json()['status'] == "ok":
                        break
                    else:
                        time.sleep(10)

                results = response.json()['results']
                
                for keyword, region_wsqso in list(results.items()):
                    if int(region_wsqso) < 3:
                        del results[keyword]
                data_list = []
                for keyword, region_wsqso in list(results.items()):
                    keyword = re.sub(r'["\'!\[\]]', '', keyword)
                    phrase = phrase.replace(" купить", "")
                    data_list.append([phrase, keyword, region_wsqso])

            sorted_data_list = sorted(data_list, key=lambda x: int(x[2]), reverse=True)

            # Записываем данные из списка в CSV файл
            writer.writerows(sorted_data_list)

            # Создаем тело запроса
            payload = {
                "token": API_KEY_WORDKEEPER,
                "id": result_id
            }

            # Отправляем POST-запрос на API
            response = requests.post('https://word-keeper.ru/api/remove', json=payload)

    url_list = []
