from pony.orm import Database, Required, Json
from settings import DB_CONFIG

db = Database()

db.bind(**DB_CONFIG)


class UserState(db.Entity):
    """Состояние пользователя внутри сценария. """
    user_id = Required(str, unique=True)
    scenario_name = Required(str)
    step_name = Required(str)
    context = Required(Json)


class TicketsOrders(db.Entity):
    """Люди забронировавшие билеты"""
    phone_number = Required(str)
    flight_number = Required(str)
    date = Required(str)
    origin = Required(str)
    destination = Required(str)
    number_of_seats = Required(str)


db.generate_mapping(create_tables=True)
