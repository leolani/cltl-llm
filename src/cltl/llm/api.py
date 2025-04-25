import abc


class LLM(abc.ABC):
    def respond(self, statement: str) -> str:
        raise NotImplementedError("")
