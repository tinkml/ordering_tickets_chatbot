from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch, Mock, ANY

from pony.orm import db_session, rollback
from vk_api.bot_longpoll import VkBotMessageEvent

import settings
from bot import Bot
from generate_ticket import generate_ticket


def isolate_bd(test_func):
    def wrapper(*args, **kwargs):
        with db_session:
            test_func(*args, **kwargs)
            rollback()

    return wrapper


class Test1(TestCase):
    RAW_EVENT = {'type': 'message_new',
                 'object': {'message':
                                {'date': 1588669205, 'from_id': 73047856, 'id': 41,
                                 'out': 0, 'peer_id': 73047856, 'text': 'Привет', 'conversation_message_id': 41,
                                 'fwd_messages': [], 'important': False, 'random_id': 0, 'attachments': [],
                                 'is_hidden': False},
                            'client_info':
                                {'button_actions': ['text', 'vkpay', 'open_app', 'location', 'open_link'],
                                 'keyboard': True, 'inline_keyboard': True, 'lang_id': 0}},
                 'group_id': 194984043,
                 'event_id': 'a71fd1c95314016d1e476eaebae9193d06ed1535'}

    def test_run(self):
        count = 5
        events = [{}] * count
        long_poller_mock = Mock(return_value=events)
        long_poller_listen_mock = Mock()
        long_poller_listen_mock.listen = long_poller_mock
        with patch('bot.vk_api.VkApi'):
            with patch('bot.VkBotLongPoll', return_value=long_poller_listen_mock):
                bot = Bot('', '')
                bot.on_event = Mock()
                bot.send_image = Mock()
                bot.run()

                bot.on_event.assert_called()
                bot.on_event.assert_any_call({})
                assert bot.on_event.call_count == count

    INPUTS = [
        'Привет',
        'Хочу заказать билет',
        'Сургут',
        'Москва',
        '21июня20',
        '2020 06 05',
        '1',
        'Да',
        '89088918290']

    ticket_data = f'Информация по билету:\n' \
                  f'Сургут - Москва\n' \
                  f'Дата вылета: 2020-06-05\n' \
                  f'Номер рейса: 119\n' \
                  f'Время вылета: 18:40\n' \
                  f'Время прибытия: 04:55\n' \
                  f'Количество пересадок: 1\n' \
                  f'Стоимость: 7649 руб\n' \
                  f'\nКоличество мест - 1\n' \
                  f'Общая стоимость: 7649\n' \
                  f'Вы подтверждаете данные?.\n' \
                  f'Напишите "Да" для подтверждения и "Нет" для отмены.'

    EXPECTED_OUTPUTS = [
        settings.DEFAULT_ANSWER,
        settings.SCENARIOS['air_flight_ticket']['steps']['step1']['text'],
        settings.SCENARIOS['air_flight_ticket']['steps']['step2']['text'],
        settings.SCENARIOS['air_flight_ticket']['steps']['step3']['text'],
        settings.SCENARIOS['air_flight_ticket']['steps']['step3']['failure_text'],
        settings.SCENARIOS['air_flight_ticket']['steps']['step4']['text'],
        ticket_data,
        settings.SCENARIOS['air_flight_ticket']['steps']['step6']['text'],
        settings.SCENARIOS['air_flight_ticket']['steps']['step7']['text']
    ]

    @isolate_bd
    def test_run_ok(self):
        send_mock = Mock()
        api_mock = Mock()
        api_mock.messages.send = send_mock

        events = []
        for input_text in self.INPUTS:
            event = deepcopy(self.RAW_EVENT)
            event['object']['message']['text'] = input_text
            events.append(VkBotMessageEvent(event))

        long_poller_mock = Mock()
        long_poller_mock.listen = Mock(return_value=events)

        with patch('bot.VkBotLongPoll', return_value=long_poller_mock):
            bot = Bot('', '')
            bot.api = api_mock
            bot.send_image = Mock()
            bot.run()

        assert send_mock.call_count == len(self.INPUTS)

        real_outputs = []
        for call in send_mock.call_args_list:
            args, kwargs = call
            real_outputs.append(kwargs['message'])
        assert real_outputs == self.EXPECTED_OUTPUTS

    CONTEXT = {
        "date": "2020-06-21",
        "origin": "SGC",
        "destination": "MOW",
        "origin_name": "Сургут",
        "flight_number": "260",
        "number_of_seats": "2",
        "destination_name": "Москва",
        "departure_at": "2020-06-21T06:00:00Z",
        "return_at": "2020-06-22T04:55:00Z",
        "phone": "89088918290"}

    def test_image_generation(self):
        with open('files/89088918290.png', 'rb') as avatar:
            avatar_mock = Mock()
            avatar_mock.content = avatar.read()
        with patch('requests.get', return_value=avatar_mock):
            ticket_file = generate_ticket(self.CONTEXT)
        with open('files/ticket_example.png', 'rb') as example:
            image_bytes = example.read()
            assert ticket_file.read() == image_bytes
