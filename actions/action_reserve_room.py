from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

import sqlalchemy as sa
from sqlalchemy.ext.declarative


class ActionReserveRoom(Action):
    def name(self) -> Text:
        return "action_reserve_room"
    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> List[Dict]:

        room_start_time = tracker.get_slot("room_start_time")
        room_end_time = tracker.get_slot("room_end_time")
        room_id = tracker.get_slot("room_id")
        m_topic = tracker.get_slot("topic")


        return []
