from rasa_sdk.knowledge_base.storage import InMemoryKnowledgeBase
from rasa_sdk.knowledge_base.actions import ActionQueryKnowledgeBase

import typing
from rasa_sdk.events import SlotSet, UserUtteranceReverted
from rasa_sdk.knowledge_base.utils import (
    SLOT_OBJECT_TYPE,
    SLOT_LAST_OBJECT_TYPE,
    SLOT_ATTRIBUTE,
    reset_attribute_slots,
    SLOT_MENTION,
    SLOT_LAST_OBJECT,
    SLOT_LISTED_OBJECTS,
    get_object_name,
    get_attribute_slots,
)
from rasa_sdk import utils
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.interfaces import Tracker

if typing.TYPE_CHECKING:  # pragma: no cover
    from rasa_sdk.types import DomainDict

import os
import json
import logging
from typing import Any, Text, Dict, List

logger = logging.getLogger(__name__)

# class ActionQueryKB(ActionQueryKnowledgeBase):
#     def name(self) -> Text:
#         retur "action_query_kb"

#     def __init__(self):
#         filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
#         self.knowledge_base = InMemoryKnowledgeBase(filepath)
filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')

print(filepath)
