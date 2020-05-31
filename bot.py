import json
import random

import logging

import requests
import vk_api
from pony.orm import db_session
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType

import handlers
from models import UserState, TicketsOrders

try:
    import settings
except ImportError:
    exit('Необходимо скопировать settings.py.default')

log = logging.getLogger('bot')


def configure_logging():
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    log.addHandler(stream_handler)
    stream_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(filename='bot.log', encoding='utf8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    log.addHandler(file_handler)
    file_handler.setLevel(logging.DEBUG)
    log.setLevel(logging.DEBUG)


class Bot:
    """
    Использован python 3.8
    """

    def __init__(self, group_id, token):
        """
        :param group_id: group_id из группы вк
        :param token: секретный токен из той же группы
        """
        self.group_id = group_id
        self.token = token
        self.vk = vk_api.VkApi(token=token)
        self.vk_longpoller = VkBotLongPoll(self.vk, self.group_id)
        self.api = self.vk.get_api()

    def run(self):
        """ Запуск бота """
        for event in self.vk_longpoller.listen():
            try:
                self.on_event(event)
            except Exception:
                log.exception('Ошибка при обработке события')

    @db_session
    def on_event(self, event):
        """
        Отправляет сообщение назад пользователю
        :param event: VkBotMessageEvent object
        :return: None
        """
        if event.type != VkBotEventType.MESSAGE_NEW:
            log.info(f'Не умеем пока обрабатывать это событие {event.type}')
            return
        text = event.message.text
        user_id = event.message.peer_id

        state = UserState.get(user_id=str(user_id))

        if state is not None:
            self.continue_scenario(text, state, user_id)
        else:
            # search intent
            for intent in settings.INTENTS:
                log.debug(f'User gets {intent}')
                if any(token in text.lower() for token in intent['tokens']):
                    # run intent
                    if intent['answer']:
                        self.send_text(intent['answer'], user_id)
                    else:
                        self.start_scenario(intent['scenario'], user_id, text)
                    break
            else:
                self.send_text(settings.DEFAULT_ANSWER, user_id)

    def send_text(self, text_to_send, user_id):
        self.api.messages.send(
            message=text_to_send,
            random_id=random.randint(0, 2 ** 20),
            peer_id=user_id)

    def send_image(self, image, user_id):
        upload_url = self.api.photos.getMessagesUploadServer()['upload_url']
        upload_data = requests.post(url=upload_url, files={'photo': ('image.png', image, 'image/png')}).json()
        image_data = self.api.photos.saveMessagesPhoto(**upload_data)
        owner_id = image_data[0]['owner_id']
        media_id = image_data[0]['id']
        ticket = f'photo{owner_id}_{media_id}'
        self.api.messages.send(
            attachment=ticket,
            random_id=random.randint(0, 2 ** 20),
            peer_id=user_id)

    def send_step(self, step, user_id, text, context):
        if 'text' in step:
            self.send_text(step['text'].format(**context), user_id)
        if 'image' in step:
            handler = getattr(handlers, step['image'])
            image = handler(text, context)
            self.send_image(image, user_id)

    def start_scenario(self, scenario_name, user_id, text):
        scenario = settings.SCENARIOS[scenario_name]
        first_step = scenario['first_step']
        step = scenario['steps'][first_step]
        self.send_step(step, user_id, text, context={})
        UserState(scenario_name=scenario_name, step_name=first_step, context={}, user_id=str(user_id))

    def continue_scenario(self, text, state, user_id):
        steps = settings.SCENARIOS[state.scenario_name]['steps']
        step = steps[state.step_name]
        handler = getattr(handlers, step['handler'])
        return_data = handler(text=text, context=state.context)
        if return_data and isinstance(return_data, bool):
            # next step
            if step['request'] is not None:
                request = getattr(handlers, step['request'])
                response = request(context=state.context)
                if response and isinstance(response, bool):
                    pass
                else:
                    state.delete()
                    self.send_text(response, user_id)
            next_step = steps[step['next_step']]
            self.send_step(next_step, user_id, text, state.context)
            if next_step['next_step']:
                # switch to next step
                state.step_name = step['next_step']
            else:
                # finish scenario
                TicketsOrders(
                    phone_number=state.context['phone'],
                    flight_number=state.context['flight_number'],
                    date=state.context['date'],
                    origin=state.context['origin_name'],
                    destination=state.context['destination_name'],
                    number_of_seats=state.context['number_of_seats']
                )
                state.delete()
        elif isinstance(return_data, str):
            # если вернулось строка
            self.send_text(return_data, user_id)
            if return_data == 'Поиск билетов отменен.\nОтправьте сообщение, чтобы начать диалог.':
                state.delete()
            else:
                state.step_name = step['half_step'] # для использования другого обработчика
        else:
            # current step
            text_to_send = step['failure_text'].format(**state.context)
            self.send_text(text_to_send, user_id)


if __name__ == '__main__':
    configure_logging()
    bot = Bot(settings.GROUP_ID, settings.TOKEN)
    bot.run()

