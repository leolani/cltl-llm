import logging
import random
from typing import List
import time
import os
from emissor.representation.scenario import class_type
from cltl.commons.language_data.sentences import GREETING, GOODBYE
from cltl.combot.infra.config import ConfigurationManager
from cltl.combot.infra.event import Event, EventBus
from cltl.combot.infra.resource import ResourceManager
from cltl.combot.infra.time_util import timestamp_now
from cltl.combot.infra.topic_worker import TopicWorker
from cltl.llm.api import LLM
from cltl.combot.event.emissor import TextSignalEvent
from cltl_service.emissordata.client import EmissorDataClient
from emissor.representation.scenario import TextSignal
from cltl.emissordata.api import EmissorDataStorage

logger = logging.getLogger(__name__)
sleep_time = 3


class LLMService:
    @classmethod
    def from_config(cls, llm: LLM, emissor_client: EmissorDataClient,
                    event_bus: EventBus, resource_manager: ResourceManager,
                    config_manager: ConfigurationManager, emissor_storage: EmissorDataStorage):

        config = config_manager.get_config("cltl.llm")
        input_topic = config.get("topic_input")
        output_topic = config.get("topic_output")
        topic_scenario = config.get("topic_scenario") if "topic_scenario" in config else None

        intention_topic = config.get("topic_intention") if "topic_intention" in config else None
        intentions = config.get("intentions", multi=True) if "intentions" in config else []

        return cls(input_topic, output_topic, topic_scenario,
                   intention_topic, intentions,
                   llm,  emissor_client, event_bus, resource_manager, emissor_storage)

    def __init__(self, input_topic: str, output_topic: str, scenario_topic: str,
                 intention_topic: str, intentions: List[str],
                 llm: LLM,  emissor_client: EmissorDataClient,
                 event_bus: EventBus, resource_manager: ResourceManager, emissor_storage: EmissorDataStorage):
        self._llm = llm
        self._event_bus = event_bus
        self._resource_manager = resource_manager
        self._emissor_client = emissor_client
        self._emissor_storage = emissor_storage
        self._input_topic = input_topic
        self._output_topic = output_topic
        self._scenario_topic = scenario_topic
        self._intentions = intentions if intentions else ()
        self._intention_topic = intention_topic if intention_topic else None
        self._topic_worker = None
        self._text_intro = llm.intro
        self._text_stop = llm.stop

    @property
    def app(self):
        return None

    def start(self, timeout=30):
        self._topic_worker = TopicWorker(
            [self._input_topic, self._scenario_topic, self._intention_topic], self._event_bus,
            provides=[self._output_topic],
            intention_topic=self._intention_topic, intentions=self._intentions,
            resource_manager=self._resource_manager, processor=self._process,
            name=self.__class__.__name__)
        self._topic_worker.start().wait()

    def stop(self):
        if not self._topic_worker:
            pass
        self._topic_worker.stop()
        self._topic_worker.await_stop()
        self._topic_worker = None

    def _process(self, event: Event):
        if event.metadata.topic == self._scenario_topic:
            human = event.payload.scenario.context.speaker
            if human:
                self._llm._set_human(human.name)
            self.play_intro()
            return

        if event.metadata.topic == self._input_topic:
            if self._stop_keyword(event.payload.signal.text.lower()):
                self._stop_script()
            else:
                input = event.payload.signal.text
                response = self._llm.respond(input)
                llm_event = self._create_payload(response)
                self._event_bus.publish(self._output_topic, Event.for_payload(llm_event))

    def play_intro(self):
        for response in self._text_intro.split("."):
            signal = TextSignal.for_scenario(self._emissor_client.get_current_scenario_id(), timestamp_now(),
                                             timestamp_now(), None,
                                             response)
            self._event_bus.publish(self._output_topic,
                                    Event.for_payload(TextSignalEvent.for_agent(signal)))
            time.sleep(sleep_time)

    def play_next(self):
        for response in self._text_next:
            signal = TextSignal.for_scenario(self._emissor_client.get_current_scenario_id(), timestamp_now(),
                                             timestamp_now(), None,
                                             response)
            self._event_bus.publish(self._output_topic,
                                    Event.for_payload(TextSignalEvent.for_agent(signal)))
            time.sleep(sleep_time)

    def _stop_keyword(self, utterance):
        for goodbye in GOODBYE:
            if goodbye.lower() in utterance.lower():
                return True
        return False

    def _stop_script(self):
        time.sleep(sleep_time)
        for response in self._text_stop.split("."):
            signal = TextSignal.for_scenario(self._emissor_client.get_current_scenario_id(), timestamp_now(),
                                             timestamp_now(), None,
                                             response)
            self._event_bus.publish(self._output_topic,
                                    Event.for_payload(TextSignalEvent.for_agent(signal)))
            time.sleep(sleep_time)
        self._emissor_storage.flush()

    def _create_payload(self, response):
        scenario_id = self._emissor_client.get_current_scenario_id()
        signal = TextSignal.for_scenario(scenario_id, timestamp_now(), timestamp_now(), None, response)

        return TextSignalEvent.for_agent(signal)

    def _is_llm_intention(self, event):
        return (event.metadata.topic == self._intention_topic
                and hasattr(event.payload, "intentions")
                and any(intention.label in self._intentions for intention in event.payload.intentions))

    def _keyword(self, event):
        if event.metadata.topic == self._input_topic:
            return any(event.payload.signal.text.lower() == bye.lower() for bye in GOODBYE)

        return False

    def _greeting_payload(self):
        scenario_id = self._emissor_client.get_current_scenario_id()
        signal = TextSignal.for_scenario(scenario_id, timestamp_now(), timestamp_now(), None,
                                         random.choice(GOODBYE))

        return TextSignalEvent.for_agent(signal)
