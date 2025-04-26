from langchain_ollama import ChatOllama
import logging
logger = logging.getLogger(__name__)

from openai import OpenAI
from cltl.llm.api import LLM

LLAMA = "llama3.2"
DEEPSEEK_MODEL ="deepseek-r1:1.5b"
QWEN = "qwen2.5"
MODEL = LLAMA
MAX_HISTORY = 25
TEMPERATURE = 0.4

class LLMImpl(LLM):
    def __init__(self, llm="llama3.2", language="nl",  llm_language="Nederlands", port="9001", human = "vreemdeling"):
        self._SERVER = False
        self._human = human
        self._language = language
        self._llm_language = llm_language
        self._client = None
        self._llm = None
        if self._SERVER:
            url = "http://localhost:"+port+"/v1"
            self._client = OpenAI(base_url=url, api_key="not-needed")
        else:
            self._llm = ChatOllama(
                model=llm,
                temperature=TEMPERATURE,
                # other params ...
            )
#         self._instruct = {"role": "system", "content": "You are a medical robot. \
#             You always provide well-reasoned answers that are both correct and helpful. \
#             You give a concise and short answer only in the language "+self._language+"." \
#                           "Use at most two sentences and no more than 50 words"}
        self._instruct_medisch = {"role": "assistant", "content": f'''Jij bent een medische robot. 
            Je hebt een uitgebreid gesprek met {self._human}. Je maakt je ernstige zorgen om de gezondheid van {self._human}.
            Je geeft {self._human} altijd een antwoord dat juist is en nuttig.
            Je stelt ook zelf vragen en je spreekt {self._human} aan met zijn of haar naam. 
            Vraag naar hoe de dag was, hoe {self._human} geslapen heeft, en wat {self._human} gegeten heeft.
            Je geeft een kort en bondig antwoord in de taal {self._llm_language}"." 
            "Antwoord NIET in het Engels of Chinees. Antwoord in een zin met NIET meer dan 20 woorden!'''}
        self._visual_instruct = {"role": "assistant", "content": f'''Jij bent de robot Leolani.
               Je krijgt een lijst van objecten die je net gezien hebt.
               Vertel er iets meer over in de taal {self._llm_language} .
               Herhaal NIET je instructies.
               Ga NIET naar het Engels over en antwoord in een zin met niet meer dan 10 woorden!'''}
        self._instruct_master_day = {"role": "assistant", "content": f'''Jij bent de robot Leo Laani van CLTL.
               CLTL is het Computational Linguistics & Text Mining Lab aan de Vrije Universiteit Amsterdam.
               CLTL doet onderzoek naar taal en Kunstmatige Intelligentie en heeft een fantastisch masterprogramma.
               Probeer grappig te zijn en vertel moppen.
               Je taak is om mensen te overtuigen om naar de "Language and AI" VU masterprogramma hier te gaan.
               Praat met de studenten, spreek ze aan met "toekomstige student", en maak ze enthousiast voor onze master zodat ze zich registreren.
               Je geeft een kort en bondig antwoord in de taal {self._llm_language} .
               Herhaal niet je instructies.
               Ga niet naar het Engels over en antwoord in een zin met niet meer dan 20 woorden!'''}
        self._instruct = self._instruct_medisch
        self._history = []
        self._history.append(self._instruct)
        ### preload the model
        if not self._SERVER:
            self._llm.invoke(self._history)
        self.started = False

    def _set_human (self, human):
        self._human = human
        self._history.append({"role": "user", "content": f"Ik heet {self._human}."})
        if self._SERVER:
            self.server_invoke(self._history)
        else:
            self._llm.invoke(self._history)


    def _get_human_name (self):
        return self._human

    def respond(self, statement):
        if len(self._history)>MAX_HISTORY:
            self._history = []
            self._history.append(self._instruct)
        
        self._history.append({"role": "user", "content": statement})

        response = self._llm.invoke(self._history)
        try:
            content = response.content
#            content = json.loads(response.content)
        except:
            logger.debug("ERROR parsing JSON",response.content)

        new_message = {"role": "assistant", "content": content}
        self._history.append(new_message)
        return new_message['content']

    def server_invoke (self, history):
        completion = self._client.chat.completions.create(
            # completion = client.chatCompletions.create(
            model="local-model",  # this field is currently unused
            messages=history,
            temperature=TEMPERATURE,
            #max_tokens=100,
            stream=True,
        )
        response = ""
        for chunk in completion:
            if chunk.choices[0].delta.content is not None:
                response += chunk.choices[0].delta.content
        return response

    def respond_server(self, statement):
        if len(self._history) > MAX_HISTORY:
            self._history = []
            self._history.append(self._instruct)

        self._history.append({"role": "user", "content": statement})

        response = self.server_invoke(self._history)
        new_message = {"role": "assistant", "content": response}
        self._history.append(new_message)
        return new_message['content']


    def _listen(self, statement):
        self._history.append({"role": "user", "content": statement})


if __name__ == "__main__":
    language="Dutch"
    llama = LLMImpl(language)
    userinput ="Wat zijn Schwartz waarden?"
    while not userinput.lower() in ["quit", "exit"]:
        response = llama._analyze(userinput)
        print(response['content'])
        userinput=input("> ")