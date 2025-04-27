from langchain_ollama import ChatOllama
import logging
logger = logging.getLogger(__name__)
from openai import OpenAI
from cltl.llm.api import LLM
from cltl.llm.prompts.prompts import PROMPTS

LLAMA = "llama3.2"
DEEPSEEK_MODEL ="deepseek-r1:1.5b"
QWEN = "qwen2.5"
MODEL = LLAMA
MAX_HISTORY = 25
TEMPERATURE = 0.4

class LLMImpl(LLM):
    def __init__(self,  instruction: PROMPTS._instruct_medical_dutch, llm="llama3.2", llm_language="English", port="9001", human = "stranger", server= False):
        self._SERVER = server
        self._human = human
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

        self._instruct = instruction
        self._history = []
        self._history.append(self._instruct)
        ### preload the model
        if not self._SERVER:
            self._llm.invoke(self._history)
        self.started = False

    def _set_instruct (self, instruct):
        self._instruct = instruct

    def _set_language (self, language: str):
        self._llm_language = language

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
    language="Nederlands"
    prompts = PROMPTS(llm_language=language, human_name="Fred")
    llm = LLMImpl(llm_language=language, instruction=prompts._instruct_medical_dutch, server=False)
    userinput ="Ik ben misselijk?"
    while not userinput.lower() in ["quit", "exit"]:
        response = llm.respond(userinput)
        print(response)
        userinput=input("> ")