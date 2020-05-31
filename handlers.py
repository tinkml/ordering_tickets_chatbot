"""
handler - функция, которая принимает на вход text (текст входящего сообщения) и context (dict), а возвращает bool:
True - если шаг пройден, False - если данные введены неправильно.
"""
import json
import re

import requests
from settings import TOKEN_AVIASALES
from generate_ticket import generate_ticket

re_phone = re.compile(r"\d{11}")


def country_code_to_name(country_code):
    with open('geo_data/countries.json', 'r', encoding='utf8') as countries_data:
        countries = json.load(countries_data)
        for country in countries:
            if country_code == country['code']:
                return country['name']


def get_code(data, context):
    countries_codes = dict(*data.values())
    countries_name = list(*data.values())
    if len(countries_codes) > 1:
        text_to_send = f'Данный город, есть в нескольких странах:\n'
        for number, country in enumerate(countries_name):
            text_to_send += f'{number} | {country}\n'
        text_to_send += f'Введите порядоквый номер необходимой страны'
        context['countries_codes'] = countries_codes
        context['countries_name'] = countries_name
        return text_to_send
    elif len(countries_name) == 1:
        code = str(*countries_codes.values())
        if 'origin' in context:
            context['destination'] = code
        else:
            context['origin'] = code
        return True
    else:
        return False


def handle_city(text, context):
    with open('geo_data/cities.json', 'r', encoding='utf8') as flights_data:
        flights = json.load(flights_data)
        cities_data = {}
        for flight in flights:
            city = flight['name']
            city_code = flight['code']
            country_code = flight['country_code']
            if city is not None and city.lower() == text.strip().lower():
                country_name = country_code_to_name(country_code)
                codes = {country_name: city_code}
                if city in cities_data:
                    cities_data[city].update(codes)
                else:
                    cities_data[city] = codes
        if 'origin_name' in context:
            context['destination_name'] = text.strip().capitalize()
        else:
            context['origin_name'] = text.strip().capitalize()
        return get_code(cities_data, context)


def choose_city(text, context):
    if text.isdigit():
        country = context['countries_name'][int(text)]
        code = context['countries_codes'][country]
        if 'origin' in context:
            context['destination'] = code
        else:
            context['origin'] = code
        return True
    else:
        return False


def get_response(context):
    origin = context['origin']
    destination = context['destination']
    main_request = f'http://api.travelpayouts.com/v1/prices/calendar?origin={origin}' \
                   f'&destination={destination}&calendar_type=departure_date'
    response = requests.get(main_request, headers={"X-Access-Token": f"{TOKEN_AVIASALES}"})
    air_flight_data = json.loads(response.text)
    if air_flight_data['success']:
        if len(air_flight_data['data']) != 0:
            context['air_flight_data'] = air_flight_data
            return True
        else:
            text_to_send = 'Нет ни одного рейса, между этими городами.'
    else:
        text_to_send = 'Вы ввели не верные данные. Попробуйте снова'
    return text_to_send


def search_for_nearest_dates(user_date, dates_list):
    if len(dates_list) <= 5:
        nearest_dates = dates_list
    else:
        nearest_dates = []
        for response_date in dates_list:
            if response_date[:-3] > user_date[:-3]:
                if len(nearest_dates) != 5:
                    nearest_dates.append(response_date)
                else:
                    break
            elif response_date[:-3] == user_date[:-3]:
                nearest_dates.append(response_date)
        if len(nearest_dates) == 0:
            nearest_dates.extend(dates_list[-5:])
        elif len(nearest_dates) != 5:
            nearest_dates.extend(dates_list[-5:-len(nearest_dates)])
    return sorted(nearest_dates)


def check_flight(input_date, input_data, context):
    if input_date in input_data['data']:
        final_date = input_date
        context['date'] = final_date
        return True
    elif input_date not in input_data['data']:
        response_dates = list(input_data['data'].keys())
        nearest_date = search_for_nearest_dates(input_date, response_dates)
        text_to_send = f'К сожалению, такое рейса нету.\nНо есть следующие рейсы:\n'
        for number, dates in enumerate(nearest_date):
            text_to_send += f'{number} | {dates}\n'
        text_to_send += f'Введите порядковый номер даты.'
        context['nearest_date'] = nearest_date
        return text_to_send
    else:
        return False


def get_date(text, context):
    re_date = r'([0-9]{4})[\s\-\.\\\/](0[1-9]|1[012])[\s\-\.\\\/]*(0[1-9]|1[0-9]|2[0-9]|3[01])*'
    _re_date = re.search(re_date, text)
    if _re_date is not None:
        date = f'{_re_date[1]}-{_re_date[2]}-{_re_date[3]}'
        input_data = context['air_flight_data']
        return check_flight(date, input_data, context)
    else:
        return False


def choose_date(text, context):
    if text.isdigit():
        final_date = context['nearest_date'][int(text)]
        context['date'] = final_date
        return True
    else:
        return False


def show_ticket_information(text, context):
    date = context['date']
    data = context['air_flight_data']['data']
    origin_name = context['origin_name']
    destination_name = context['destination_name']
    price = data[date]['price']
    transfers = data[date]['transfers']
    flight_number = data[date]['flight_number']
    context['flight_number'] = str(flight_number)
    context['number_of_seats'] = str(text)
    departure_at = data[date]['departure_at']
    context['departure_at'] = str(departure_at)
    return_at = data[date]['return_at']
    context['return_at'] = str(return_at)
    text_to_send = f'Информация по билету:\n' \
                   f'{origin_name} - {destination_name}\n' \
                   f'Дата вылета: {date}\n' \
                   f'Номер рейса: {flight_number}\n' \
                   f'Время вылета: {departure_at[11:16]}\n' \
                   f'Время прибытия: {return_at[11:16]}\n' \
                   f'Количество пересадок: {transfers}\n' \
                   f'Стоимость: {price} руб\n' \
                   f'\nКоличество мест - {text}\n' \
                   f'Общая стоимость: {int(price) * int(text)}\n' \
                   f'Вы подтверждаете данные?.\n' \
                   f'Напишите "Да" для подтверждения и "Нет" для отмены.'
    context.pop('air_flight_data')
    return text_to_send


def admit_data(text, context):
    if text.strip().lower() == 'да':
        return True
    elif text.strip().lower() == 'нет':
        text_to_send = f'Вы хотите начать поиск билетов заново?\nНапишите "Да" для подтверждения и "Нет" для отмены.'
        return text_to_send
    else:
        return False


def restart(text, context):
    if text.strip().lower() == 'да':
        return True
    elif text.strip().lower() == 'нет':
        text_to_send = f'Поиск билетов отменен.\nОтправьте сообщение, чтобы начать диалог.'
        return text_to_send
    else:
        return False


def handle_phone(text, context):
    match = re.search(re_phone, text)
    if match:
        context['phone'] = str(text)
        return True
    else:
        return False


def ticket(text, context):
    return generate_ticket(context=context)
