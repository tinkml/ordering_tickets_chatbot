from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageFont

TEXT_COLOR = (25, 25, 25)
MAIN_FONT = ImageFont.truetype("files/font/Roboto-Regular.ttf", size=14)
AVATAR_SIZE = '216'


def generate_ticket(context):
    origin = context['origin']
    destination = context['destination']
    date = context['date']
    origin_name = context['origin_name']
    destination_name = context['destination_name']
    departure_at = context['departure_at']
    return_at = context['return_at']
    phone = context['phone']
    number_of_seats = context['number_of_seats']

    base = Image.new('RGB', (512, 256), (245, 245, 245))
    ticket = ImageDraw.Draw(base)
    ticket.rectangle(xy=[6, 6, 506, 250], outline=(110, 110, 110), width=2)

    short_data = f'{origin} / {destination} - {date}'
    ticket.text((18, 18), text=short_data, font=MAIN_FONT, fill=TEXT_COLOR)

    origin_data = f'{origin_name} {origin}\n{departure_at}'
    ticket.text((18, 56), text=origin_data, font=MAIN_FONT, fill=TEXT_COLOR)

    y = 96
    for line in range(6):
        ticket.text((18, y), text='|', font=MAIN_FONT, fill=TEXT_COLOR)
        y += 14

    destination_data = f'{destination_name} {destination}\n{return_at}'
    ticket.text((18, 192), text=destination_data, font=MAIN_FONT, fill=TEXT_COLOR)

    response = requests.get(url=f'https://api.adorable.io/avatars/{AVATAR_SIZE}/{phone}.png')
    avatar_file_like = BytesIO(response.content)

    avatar = Image.open(avatar_file_like)
    base.paste(avatar, (278, 18))
    seats = f'{number_of_seats:>5} x'
    ticket.text((244, 18), text=seats, font=MAIN_FONT, fill=TEXT_COLOR)

    ticket_like_file = BytesIO()
    base.save(ticket_like_file, 'png')
    ticket_like_file.seek(0)
    return ticket_like_file


if __name__ == '__main__':
    context = {
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
    print(generate_ticket(context))
