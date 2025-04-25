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

text_end_master = ["Als je meer wil weten over taaltechnologie en AI ga dan naar zaal HG-1A-43 om 13:00 uur voor de ""Language and AI"" master.",
               "Je  kunt ook om 14:00 naar de Onderzoeksmaster ""Humanities"" gaan en dan naar de ""Language Technology track"" in OG23 in het filosofenhof.",
               "Misschien zie ik je daar!",
               "Hennie van der Vliet van CLTL zal al je vragen  beantwoorden over ons masterprogramma."]

text_start_master = ["Hallo daar, welkom op de Vrije Universiteit Amsterdam.", "Waarmee kan ik je helpen?"]

text_intro_robert = ["Ik wil graag een verkennend gesprek met je voeren in opdracht van de volgende geestelijke gezondheidsorganisaties:", "Arkin, huisartsengroep ROHA, Amsterdam UMC, en Zilveren Kruis.",
              "Ik registreer het gesprek in de verschillende EPD’s en ECD’s.", "Dit zal administratieve lastenverlichting in de zorg geven."]
text_next_robert = ["De informatie die ik verzamel is uitsluitend bedoeld voor de huisarts.","Het zal dan ook alleen bij de huisarts terechtkomen en niet bijvoorbeeld bij je woningcorporatie.",
             "Integriteit, gegevenscoördinatie en privacy zijn belangrijk.",
             "De volgende keer wil ik in ons gesprek ook graag een symptomen check doen.",
             "Na het gesprek kan ik de gegevens analyseren met de zorgprofessional.", "De volgende dag volgt daar dan een bericht over.",
             "Ik ga nu een gesprek met je voeren over je gezondheid. Ik gebruik daarvoor een open-source AI model Lama.",
             "Hoe voel je je vandaag?"]

text_out_robert = ["Het laatste stukje van het gesprek heb ik dus gevoerd met de hulp van AI.",
            "Het klinkt best goed ook al is de AI niet bewust met Nederlandse data getraind.",
            "Het probleem is echter dat we geen controle hebben over de antwoorden die de AI geeft.",
            "De training is vooral gebaseerd op Amerikaanse gezondheidsprotocollen en Engelse data.",
            "Nederlandse protocollen en persoonlijke informatie van een patiënt worden niet meegenomen bij het trainen.",
            "In onze oplossing willen we die controle wel behouden.", "We trainen de AI daarom met Nederlandse medische data.",
            "Ook gebruiken we een Knowledge Graph als lange termijn geheugen en om te redeneren.",
            "De Nederlandse medische praktijk en de persoonlijke omstandigheden zijn dan leidend voor de reactie van de AI.",
            "Tot ziens!"]
text_plot = ["Kijk hier! Hier zie je een plot van ons gesprek.", "De plot geeft weer wat er gezegd is door wie maar ook wat ik gezien heb en welke emoties en intenties ik heb waargenomen.",
             "Deze analyse is nuttig voor mij om te begrijpen hoe de communicatie verloopt."]

logger = logging.getLogger(__name__)

CONTENT_TYPE_SEPARATOR = ';'


_ADDRESS1 = [
    "Je zegt net: ",
    "Ik hoorde je zeggen: ",
    "Ja fascinerend je noemde: ",
    "Mag ik daar iets op zeggen? Je zei namelijk: ",
    "Zei je zojuist iets over: ",
    "Je zei zojuist iets over: "
]

_ADDRESS2 = [
    "Daar wil ik wel even op ingaan. ",
    "Daar heb ik het volgende over te zeggen. ",
    "Weet je wat ik daarvan vindt? ",
    "Volgens mijn bescheiden mening: ",
    "Ja, daar heb ik wel iets op te zeggen. ",
    "Dit is mijn commentaar hierop. ",
    "Mijn mening hierover is: ",
    "Ik zou hier het volgende aan willen toevoegen: ",
    "Tja, wat moet ik daar op zeggen? "
    
]

sleep_time = 6
_MASTER = False

class LLMService:
    @classmethod
    def from_config(cls, llm: LLM, emissor_client: EmissorDataClient,
                    event_bus: EventBus, resource_manager: ResourceManager,
                    config_manager: ConfigurationManager, emissor_storage: EmissorDataStorage):
        config = config_manager.get_config("cltl.llmn")
        langconfig = config_manager.get_config("cltl.language")

        input_topic = config.get("topic_input")
        image_topic = config.get("image.input")
        output_topic = config.get("topic_output")
        topic_scenario = config.get("topic_scenario") if "topic_scenario" in config else None

        intention_topic = config.get("topic_intention") if "topic_intention" in config else None
        intentions = config.get("intentions", multi=True) if "intentions" in config else []

        port = config.get("port")
        llm._language =  langconfig.get("language")
        llm._port = port
        return cls(input_topic, image_topic, output_topic, topic_scenario,
                   intention_topic, intentions,
                   llm, llm._language, emissor_client, event_bus, resource_manager, emissor_storage)

    def __init__(self, input_topic: str, image_topic:str, output_topic: str, scenario_topic: str,
                 intention_topic: str, intentions: List[str],
                 llm: LLM, language: "en", emissor_client: EmissorDataClient,
                 event_bus: EventBus, resource_manager: ResourceManager, emissor_storage: EmissorDataStorage):
        self._llm = llm
        self._event_bus = event_bus
        self._resource_manager = resource_manager
        self._emissor_client = emissor_client
        self._emissor_storage = emissor_storage
        self._input_topic = input_topic
        self._output_topic = output_topic
        self._image_topic = image_topic
        self._scenario_topic = scenario_topic
        self._intentions = intentions if intentions else ()
        self._intention_topic = intention_topic if intention_topic else None
        self._first_utterance = True
        self._topic_worker = None
        self._language =language
        self._text_intro = [f"Hallo {self._llm._get_human_name()}, ik ben Leolani en ik ben er om je te helpen.", "Ik luister naar je en geef je medische adviezen."]
        self._text_next = []
        self._text_stop = ["Tot ziens!", "Ik hoop je snel weer te zien."]


        
    @property
    def app(self):
        return None

    def start(self, timeout=30):
        self._topic_worker = TopicWorker([self._input_topic, self._scenario_topic, self._image_topic, self._intention_topic], self._event_bus,
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
            human =  event.payload.scenario.context.speaker
            if human:
                self._llm._set_human(human.name)
            return
        
        if event.metadata.topic == self._input_topic:
            if self._first_utterance:
                self._text_intro = [
                    f"Hallo {self._llm._get_human_name()}, ik ben Leolani en ik ben er om je te helpen.",
                    "Ik luister naar je en geef je medische adviezen.", "Vertel wat over jezelf. Wie ben je?"]
                self.play_intro()
                self._first_utterance = False
            elif self._stop_keyword(event.payload.signal.text.lower()):
                    self._stop_script()
            else:
                input = event.payload.signal.text
                response = self._llm.respond(input)
                llm_event = self._create_payload(response)
                self._event_bus.publish(self._output_topic, Event.for_payload(llm_event))


    def play_intro(self):
        for response in self._text_intro:
            signal = TextSignal.for_scenario(self._emissor_client.get_current_scenario_id(), timestamp_now(), timestamp_now(), None,
                                             response)
            self._event_bus.publish(self._output_topic,
                                    Event.for_payload(TextSignalEvent.for_agent(signal)))
            time.sleep(sleep_time)

    def play_next(self):
        for response in self._text_next:
            signal = TextSignal.for_scenario(self._emissor_client.get_current_scenario_id(), timestamp_now(), timestamp_now(), None,
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
        for response in self._text_stop:
            signal = TextSignal.for_scenario(self._emissor_client.get_current_scenario_id(), timestamp_now(), timestamp_now(), None,
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
