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

class ActionQueryKB(ActionQueryKnowledgeBase):
    def name(self) -> Text:
        return "action_query_kb"

    def __init__(self):
        filepath = os.path.join(os.path.dirname(os.path.abspath(r'.')), 'rasa_hmmcn/data/data.json')

        self.knowledge_base = InMemoryKnowledgeBase(filepath)

        self.object_type_dict = {i: [j['name'] for j in self.knowledge_base.data[i]] for i in self.knowledge_base.data}

        self.object_name_dict = {j: i for i in self.object_type_dict for j in self.object_type_dict[i]}
        self.attribute_list = list(
            set([k for i in self.knowledge_base.data for j in self.knowledge_base.data[i] for k in j]))

        super().__init__(self.knowledge_base)

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: "DomainDict",
    ) -> List[Dict[Text, Any]]:
        print('-' * 20)
        entities = tracker.latest_message.get("entities", [])
        if not entities:
            dispatcher.utter_message(template="utter_default")
            return []

        object_type = tracker.get_slot(SLOT_OBJECT_TYPE)
        last_object_type = tracker.get_slot(SLOT_LAST_OBJECT_TYPE)
        attribute = tracker.get_slot(SLOT_ATTRIBUTE)
        print(object_type, last_object_type, attribute)

        if attribute not in self.attribute_list:
            entities = tracker.latest_message.get("entities", [])
            object = list(
                filter(lambda obj: obj.get("value") in self.attribute_list and obj.get('entity') == 'attribute',
                       entities))
            if object:
                attribute = object[-1].get('value')
            else:
                attribute = None
                tracker.slots[SLOT_ATTRIBUTE] = None

        if object_type not in self.knowledge_base.data.keys():
            entities = tracker.latest_message.get("entities", [])
            k = self.knowledge_base.data.keys()
            object = list(filter(lambda obj: obj.get("entity") in k, entities))
            if object:
                object_type = object[-1].get('entity')
            else:
                object_type = None
                tracker.slots[SLOT_OBJECT_TYPE] = None

        mention = tracker.get_slot(SLOT_MENTION)
        if mention not in self.knowledge_base.ordinal_mention_mapping:
            tracker.slots[SLOT_MENTION] = None

        print(object_type, last_object_type, attribute)

        entities = tracker.latest_message.get("entities", [])
        k = self.knowledge_base.data.keys()
        object = list(filter(lambda obj: obj.get("entity") in k, entities))
        print(object)
        # 没查询到实体类型，从实体中提取实体类型
        if len(object) != 0:
            object_name = object[-1].get('value')
            object_type = self.object_name_dict.get(object_name, None)
            tracker.slots[SLOT_OBJECT_TYPE] = object_type
            if attribute:
                return await self._query_attribute(dispatcher, object_type, attribute, tracker)
            else:
                return await self._query_object(dispatcher, object_type, attribute, tracker)

        new_request = object_type != last_object_type

        if not object_type:
            dispatcher.utter_message(template="utter_default")
            return []

        if not attribute or new_request:
            return await self._query_objects(dispatcher, object_type, tracker)
        elif attribute:
            return await self._query_attribute(
                dispatcher, object_type, attribute, tracker
            )

        # dispatcher.utter_message(template="utter_ask_rephrase")
        dispatcher.utter_message(template="utter_default")
        return []

    async def _query_attribute(
            self,
            dispatcher: CollectingDispatcher,
            object_type: Text,
            attribute: Text,
            tracker: Tracker,
    ) -> List[Dict]:

        object_name = get_object_name(
            tracker,
            self.knowledge_base.ordinal_mention_mapping,
            self.use_last_object_mention,
        )
        print(object_type, object_name, attribute)
        if object_name is None or not attribute:
            dispatcher.utter_message(template="utter_default")
            return [SlotSet(SLOT_MENTION, None)]

        object_of_interest = await utils.call_potential_coroutine(
            self.knowledge_base.get_object(object_type, object_name)
        )
        if not object_of_interest or attribute not in object_of_interest:
            dispatcher.utter_message(text='Sorry, 数据库中没有{}这个属性'.format(attribute))
            return [SlotSet(SLOT_MENTION, None)]

        value = object_of_interest[attribute]

        object_representation = await utils.call_potential_coroutine(
            self.knowledge_base.get_representation_function_of_object(object_type)
        )

        key_attribute = await utils.call_potential_coroutine(
            self.knowledge_base.get_key_attribute_of_object(object_type)
        )

        object_identifier = object_of_interest[key_attribute]

        await utils.call_potential_coroutine(
            self.utter_attribute_value2(
                dispatcher, object_representation(object_of_interest), attribute, value, object_type
            )
        )

        slots = [
            SlotSet(SLOT_OBJECT_TYPE, object_type),
            SlotSet(SLOT_ATTRIBUTE, None),
            SlotSet(SLOT_MENTION, None),
            SlotSet(SLOT_LAST_OBJECT, object_identifier),
            SlotSet(SLOT_LAST_OBJECT_TYPE, object_type),
        ]

        return slots

    def utter_attribute_value2(
            self,
            dispatcher: CollectingDispatcher,
            object_name: Text,
            attribute_name: Text,
            attribute_value: Text,
            object_type: Text
    ):
        if os.path.exists("data/response.json"):
            # 如果response文件中存在该实体的该属性对应的自定义回复模板，则使用自定义回复模板
            f = open("data/response.json", "r", encoding='utf-8')
            responses = json.load(f)
            if object_type in responses.keys() and attribute_name in responses[object_type].keys() and \
                    responses[object_type][attribute_name] != "":
                response = responses[object_type][attribute_name]
                response = response.split("|")
                for i, res in enumerate(response):
                    if res == "名称":
                        response[i] = object_name
                    if res == attribute_name:
                        if isinstance(attribute_value, list):
                            response[i] = "、".join(attribute_value)
                        elif isinstance(attribute_value, bool):
                            if (attribute_value == False):
                                response[i] = "不"
                            elif (attribute_value == True):
                                response[i] = ""
                        else:
                            response[i] = attribute_value
                msg = "".join(response)
                dispatcher.utter_message(text=msg)
                return
        # 否则，使用统一回复模板
        if attribute_value:
            msg = f"{object_name}的{attribute_name}是{attribute_value}"
            if type(attribute_value) == list:
                msg = f"{object_name}的{attribute_name}是{'、'.join(attribute_value)}"
            try:
                attribute_value = int(attribute_value)
                temp = {1: '是有', 0: '是没有'}
                if attribute_name in ['预约', '学生卡']:
                    temp = {1: '是需要', 0: '是不需要'}
                if attribute_name in ['免费']:
                    temp = {1: '是', 0: '不是'}
                msg = f"{object_name}{temp[attribute_value]}{attribute_name}的"
            except:
                pass
            dispatcher.utter_message(
                text=msg
            )
        else:
            dispatcher.utter_message(
                text=f"{object_name}没有{attribute_name}"
            )

    async def utter_objects(
            self,
            dispatcher: CollectingDispatcher,
            object_type: Text,
            objects: List[Dict[Text, Any]],
    ):
        name_map = {'entertainment': '娱乐场所', 'college': '学院', 'domitary': '宿舍', 'service_building': '服务型建筑', 'canteen': '食堂'}
        if objects:
            dispatcher.utter_message(
                text=f"天津大学有以下{name_map[object_type]}:"
            )

            repr_function = await utils.call_potential_coroutine(
                self.knowledge_base.get_representation_function_of_object(object_type)
            )

            for i, obj in enumerate(objects, 1):
                dispatcher.utter_message(text=f"{i}: {repr_function(obj)}")
        else:
            dispatcher.utter_message(
                text=f"没有找到'{object_type}':"
            )

    def predict_attribute(
            self,
            user_text: Text,
    ):
        return ''

    async def _query_object(self, dispatcher, object_type, attribute, tracker):
        object_name = get_object_name(
            tracker,
            self.knowledge_base.ordinal_mention_mapping,
            self.use_last_object_mention,
        )
        print(object_type, object_name, attribute)
        if object_name is None:
            # dispatcher.utter_message(template="utter_ask_rephrase")
            dispatcher.utter_message(template="utter_default")
            return [SlotSet(SLOT_MENTION, None)]

        object_of_interest = await utils.call_potential_coroutine(
            self.knowledge_base.get_object(object_type, object_name)
        )

        object_representation = await utils.call_potential_coroutine(
            self.knowledge_base.get_representation_function_of_object(object_type)
        )

        key_attribute = await utils.call_potential_coroutine(
            self.knowledge_base.get_key_attribute_of_object(object_type)
        )

        object_identifier = object_of_interest[key_attribute]

        await utils.call_potential_coroutine(
            self.utter_attribute_value3(
                dispatcher, object_representation(object_of_interest), object_of_interest, object_type
            )
        )

        slots = [
            SlotSet(SLOT_OBJECT_TYPE, object_type),
            SlotSet(SLOT_ATTRIBUTE, None),
            SlotSet(SLOT_MENTION, None),
            SlotSet(SLOT_LAST_OBJECT, object_identifier),
            SlotSet(SLOT_LAST_OBJECT_TYPE, object_type),
        ]

        return slots

    def utter_attribute_value3(
            self,
            dispatcher: CollectingDispatcher,
            object_name: Text,
            object,
            object_type: Text
    ):
        res = object_name + '\n'
        for attribute_name in object:
            if attribute_name in ['名称', 'name', 'id']:
                continue
            attribute_value = object[attribute_name]
            msg = f"{attribute_name}是{attribute_value}，"
            if type(attribute_value) == list:
                msg = f"{attribute_name}是{'、'.join(attribute_value)}，"
            try:
                attribute_value = int(attribute_value)
                temp = {1: '是有', 0: '是没有'}
                if attribute_name in ['预约', '学生卡']:
                    temp = {1: '是需要', 0: '是不需要'}
                if attribute_name in ['免费']:
                    temp = {1: '是', 0: '不是'}
                msg = f"{temp[attribute_value]}{attribute_name}的，"
            except:
                pass
            res = res + msg
        dispatcher.utter_message(
            text=res
        )

    async def _query_objects(
            self, dispatcher: CollectingDispatcher, object_type: Text, tracker: Tracker
    ) -> List[Dict]:
        """
        Queries the knowledge base for objects of the requested object type and
        outputs those to the user. The objects are filtered by any attribute the
        user mentioned in the request.

        Args:
            dispatcher: the dispatcher
            tracker: the tracker

        Returns: list of slots
        """
        object_attributes = await utils.call_potential_coroutine(
            self.knowledge_base.get_attributes_of_object(object_type)
        )

        # get all set attribute slots of the object type to be able to filter the
        # list of objects
        attributes = get_attribute_slots(tracker, object_attributes)
        # query the knowledge base
        objects = await utils.call_potential_coroutine(
            self.knowledge_base.get_objects(object_type, attributes, 100)
        )

        await utils.call_potential_coroutine(
            self.utter_objects(dispatcher, object_type, objects)
        )

        if not objects:
            return reset_attribute_slots(tracker, object_attributes)

        key_attribute = await utils.call_potential_coroutine(
            self.knowledge_base.get_key_attribute_of_object(object_type)
        )

        last_object = None if len(objects) > 1 else objects[0][key_attribute]

        slots = [
            SlotSet(SLOT_OBJECT_TYPE, object_type),
            SlotSet(SLOT_MENTION, None),
            SlotSet(SLOT_ATTRIBUTE, None),
            SlotSet(SLOT_LAST_OBJECT, last_object),
            SlotSet(SLOT_LAST_OBJECT_TYPE, object_type),
            SlotSet(
                SLOT_LISTED_OBJECTS, list(map(lambda e: e[key_attribute], objects))
            ),
        ]

        return slots + reset_attribute_slots(tracker, object_attributes)
