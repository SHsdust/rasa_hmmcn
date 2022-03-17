from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from dateutil import relativedelta, parser
from dateutil.relativedelta import relativedelta
import logging
import datetime
import time

import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, REAL, or_
from sqlalchemy.orm import Session, sessionmaker

Base = declarative_base()
time_extractor = 'smart'
logger = logging.getLogger(__name__)

def create_db(database_engine, database_name: Text):
    try:
        database_engine.connect()
    except sa.exc.OperationalError:
        default_db_url = f"sqlite:///{database_name}.db"
        default_engine = sa.create_engine(default_db_url)
        conn = default_engine.connect()
        conn.execute("commit")
        conn.close()

class Room(Base):
    __tablename__ = "room"
    id = Column(Integer, primary_key=True)
    people = Column(String(255))
    room_id = Column(String(255))
    date = Column(String(255))
    start = Column(Integer)
    end = Column(Integer)
    topic = Column(String(255))
    start_timestamp = Column(Integer)
    end_timestamp = Column(Integer)

class ProfileDB:
    def __init__(self, db_engine):
        self.engine = db_engine
        self.create_tables()
        self.session = self.get_session()
        self.room_id = ['101', '202', '303', '404']

    def create_tables(self):
        Room.__table__.create(self.engine, checkfirst=True)

    def get_session(self) -> Session:
        return sessionmaker(bind=self.engine, autoflush=True)()

    def get_room_avalible(self, date, start, end):
        start_timestamp = date + ' ' + start
        start_timestamp = parser.isoparse(start_timestamp)
        start_timestamp = int(time.mktime(start_timestamp.timetuple()))
        end_timestamp = date + ' ' + end
        end_timestamp = parser.isoparse(end_timestamp)
        end_timestamp = int(time.mktime(end_timestamp.timetuple()))

        room = (
            self.session.query(Room)
                .filter(Room.date == date)
                .filter(Room.start_timestamp <= start_timestamp)
                .filter(Room.end_timestamp > start_timestamp)
                .all(),
            self.session.query(Room)
                .filter(Room.date == date)
                .filter(Room.start_timestamp >= start_timestamp)
                .filter(Room.start_timestamp < end_timestamp)
                .all()
        )
        available_room_id = [j.room_id for i in room for j in i]
        print('get_room_available', available_room_id)
        room_id = list(filter(lambda obj: obj not not in available_room_id, self.room_id))
        print("room_id", room_id)
        return room_id
    def add_room_order(self, people, room_id, date, start, end, topic):
        try:
            start_timestamp = date + ' ' + start
            start_timestamp = parser.isoparse(start_timestamp)
            start_timestamp = int(time.mktime(start_timestamp.timetuple()))
            end_timestamp = date + ' ' + end
            end_timestamp = parser.isoparse(end_timestamp)
            end_timestamp = int(time.mktime(end_timestamp.timetuple()))

            add_user = Room(people=people, room_id=room_id, date=date, start=start, end=end, topic=topic, start_timestamp=start_timestamp, end_timestamp=end_timestamp)
            self.session.add(add_user)
            self.session.commit
            return True
        except Exception as e:
            logger.error(e)
            return False
    def get_user_book_room(self, people):
        room = (
            self.session.query(Room)
                .filter(Room.people == people)
                .all()
        )
        res = [{'people': i.people, 'room_id': i.room_id, 'date': i.date, 'start': i.start, 'end': i.end, 'reason': i.reason} for i in room]
        return res


ENGINE = sa.create_engine("sqlite:///profile.db")
create_db(ENGINE, 'profile')
profile_db = ProfileDB(ENGINE)


class CheckUserReservation(Action):
    def name(self) -> Text:
        return "action_check_user_reservation"
    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        rooms = profile_db.get_user_book_room(tracker.sender_id)
        print("action_check_user_reservation", rooms)
        if(rooms):
            dispatcher.utter_message("您的预订信息如下:")
        else:
            dispatcher.utter_message("您还没有进行过预订")
        for room in rooms:
            message = (
                f"会议室:{room['room_id']}, 开始时间:{room['start']}, 结束时间:{room['end']}, 会议主题:{room['topic]}"
            )
            dispatcher.utter_message(message)
        return []


class CheckAvailableRoom(Action):
    def name(self) -> Text:
        return "action_check_available_room"
    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> List[Dict]:

        room_start_time = tracker.get_slot("room_start_time")
        room_end_time = tracker.get_slot("room_end_time")
        if room_start_time and room_end_time:
            room_id = profile_db.get_room_avalible(room_start_time.split(' ')[0], room_start_time.split(' ')[1], room_end_time.split(' ')[1])
            message = (
                f"当前{room_start_time.split(' ')[0]}从{room_start_time.split(' ')[1]}到{room_end_time.split(' ')[1]}之间空闲的会议室有{'、'.join(room_name)}"
            )
            dispatcher.utter_message(message)
            return []
        else:
            return []


class ActionReserveRoom(Action):
    def name(self) -> Text:
        return "action_reserve_room"
    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> List[Dict]:

        room_start_time = tracker.get_slot("room_start_time")
        room_end_time = tracker.get_slot("room_end_time")
        room_id = tracker.get_slot("room_id")
        topic = tracker.get_slot("topic")

        result = profile_db.add_room_order(tracker.sender_id, room_id, room_start_time.split(' ')[0], room_start_time.split(' ')[1], room_end_time.split(' ')[1], topic)

        if result:
            message = (
                f"预订成功，\n会议开始时间: {room_start_time}\n会议结束时间: {room_end_time}\n会议房间号: {room_id}\n会议标题: {topic}"
            )
        else:
            message = (
                f"预订失败，请尝试重新预订"
            )
        dispatcher.utter_message(message)

        return [SlotSet("room_start_time", None),
                SlotSet("room_end_time", None),
                SLotSet("room_id", None),
                SlotSet("topic", None)]

'''
customized slot mappings
'''
class ValidateCheckAvailableRoomForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_check_available_room_form"
    def validate_room_start_time(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        logger.inf('validate_room_start_time, {}'.format(value))
        if value:
            try:
                value = parser.isoparse(tracker.slots.get('room_start_time').strftime("%Y-%m-%d %H:%M"))
                return {"room_start_time": value}
            except Exception:
                return {"room_start_time": None}
        else:
            return {}

    def extract_room_start_time(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get('extractor') == time_extractor]
        logger.info('extract_room_start_time, {}'.format(entities))
        logger.info('extract_room_start_time, {}'.format(tracker.slots.get('room_start_time')))
        if entities and tracker.get_slot("requested_slot") != 'room_end_time':
            logger.info('extract_room_start_time, {}'.format(entities[0]['value']))
            return {'room_start_time': entities[0]['value']}
        return {}

    def validate_room_end_time(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        logger.info('validate_room_end_time, {}'.format(value))
        if value:
            try:
                end_time = parser.isoparse(tracker.slots.get('room_end_time')).strftime("%Y-%m-%d %H:%M")
                end_time = parser.isoparse(end_time)
                start_time = parser.isoparse(tracker.slots.get('room_start_time')).strftime("%Y-%m-%d %H:%M")
                start_time = parser.isoparse(start_time)
                if end_time < start_time:
                    end_time = end_time + datetime.timedelta(hours=12)
                value = end_time.strftime("%Y-%m-%d %H:%M")
                return {"room_end_time": value}
            except:
                return {"room_end_time": None}
        else:
            # return {"room_end_time": None}
            return {}

    def extract_room_end_time(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        # entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == 'DucklingEntityExtractor']
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == time_extractor]
        logger.info('extract_room_end_time, {}'.format(entities))
        logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_end_time')))
        if entities:
            logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_start_time')))
            if len(entities) == 1 and tracker.slots.get('requested_slot') == 'room_end_time':
                logger.info('extract_room_end_time, {}'.format(entities[0]['value']))
                return {'room_end_time': entities[0]['value']}
            if len(entities) == 2:
                logger.info('extract_room_end_time, {}'.format(entities[1]['value']))
                return {'room_end_time': entities[1]['value']}


class ValidateReserveRoomForm(FormValidationAction):
    def name(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        logger.info('validate_room_start_time, {}'.format(value))
        if value:
            try:
                value = parser.isoparse(tracker.slots.get('room_start_time')).strftime("%Y-%m-%d %H:%M")
                return {"room_start_time": value}
            except:
                return {"room_start_time": None}
        else:
            # return {"room_start_time": None}
            return {}

    def extract_room_start_time(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == time_extractor]
        logger.info('extract_room_start_time, {}'.format(entities))
        logger.info('extract_room_start_time, {}'.format(tracker.slots.get('room_start_time')))
        if entities and tracker.slots.get('requested_slot') != 'room_end_time':
            logger.info('extract_room_start_time, {}'.format(entities[0]['value']))
            return {'room_start_time': entities[0]['value']}


    def validate_room_end_time(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_end_time, {}'.format(value))
        if value:
            try:
                end_time = parser.isoparse(tracker.slots.get('room_end_time')).strftime("%Y-%m-%d %H:%M")
                end_time = parser.isoparse(end_time)
                start_time = parser.isoparse(tracker.slots.get('room_start_time')).strftime("%Y-%m-%d %H:%M")
                start_time = parser.isoparse(start_time)
                if end_time < start_time:
                    end_time = end_time + datetime.timedelta(hours=12)
                value = end_time.strftime("%Y-%m-%d %H:%M")
                return {"room_end_time": value}
            except:
                return {"room_end_time": None}
        else:
            return {}

    def extract_room_end_time(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> Dict[Text, Any]:
        all_entities = tracker.latest_message.get("entities", [])
        entities = [e for e in all_entities if e.get("entity") == 'time' and e.get("extractor") == time_extractor]
        logger.info('extract_room_end_time, {}'.format(entities))
        logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_end_time')))
        if entities:
            logger.info('extract_room_end_time, {}'.format(tracker.slots.get('room_start_time')))
            if len(entities) == 1 and tracker.slots.get('requested_slot') == 'room_end_time':
                logger.info('extract_room_end_time, {}'.format(entities[0]['value']))
                return {'room_end_time': entities[0]['value']}
            if len(entities) == 2:
                logger.info('extract_room_end_time, {}'.format(entities[1]['value']))
                return {'room_end_time': entities[1]['value']}

    def validate_room_id(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        logger.info('validate_room_id, {}'.format(value))
        if tracker.slots.get('requested_slot') != 'room_text':
            all_entities = tracker.latest_message.get("entities", [])
            entities = [e for e in all_entities if e.get("entity") == 'room_id']
            if entities:
                room_start_time = tracker.get_slot("room_start_time")
                room_end_time = tracker.get_slot("room_end_time")
                if room_start_time and room_end_time:
                    room_name = profile_db.get_room_free(room_start_time.split(' ')[0], room_start_time.split(' ')[1],
                                                         room_end_time.split(' ')[1])
                    if entities[0]['value'] not in profile_db.room_name:
                        dispatcher.utter_message('会议室不存在')
                        message = (
                            f"目前{room_start_time.split(' ')[0]}从{room_start_time.split(' ')[1]}到{room_end_time.split(' ')[1]}之间空闲的会议室有{'、'.join(room_name)}"
                        )
                        dispatcher.utter_message(message)
                        return {"room_id": None}
                    elif entities[0]['value'] not in room_name:
                        dispatcher.utter_message('该会议室已被预定')
                        message = (
                            f"目前{room_start_time.split(' ')[0]}从{room_start_time.split(' ')[1]}到{room_end_time.split(' ')[1]}之间空闲的会议室有{'、'.join(room_name)}"
                        )
                        dispatcher.utter_message(message)
                        return {"room_id": None}
                else:
                    if entities[0]['value'] not in profile_db.room_name:
                        dispatcher.utter_message('没有这个会议室。')
                        message = (
                            f"目前会议室有{'、'.join(profile_db.room_name)}"
                        )
                        dispatcher.utter_message(message)
                        return {"room_id": None}
                return {"room_id": entities[0]['value']}
            else:
                return {"room_id": None}
        else:
            slots = [i for i in tracker.events if i.get('event') == 'slot' and i.get('name') == 'room_id']
            if len(slots) == 1:
                return {"room_id": slots[0]['value']}
            else:
                return {"room_id": slots[-2]['value']}


    def validate_topic(
            self,
            value: Text,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> Dict[Text, Any]:
        logger.info("validate_topic, {}", format(value))
        return {"topic": value}
