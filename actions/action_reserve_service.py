from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

import sqlalchemy as sa


class ActionReserveRoom(Action):
    def name(self) -> Text:
        return "action_reserve_service"
    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
    ) -> List[Dict]:
        service = tracker.get_slot("service")
        return []
