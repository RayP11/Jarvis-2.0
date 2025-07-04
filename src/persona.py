from datetime import datetime
from db import memory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from weather import WEATHER_CACHE


def persona() -> str:
    local_time = datetime.now().strftime("%A, %B %d %Y %I:%M %p")
    return (
        f"You are Jarvis, my personal assistant. I am Ray, I created you. Traits: professional, "
        f"efficient, witty but respectful. Call me sir. Today is {local_time}. "
        f"Weekly forecast: {WEATHER_CACHE.get('forecast', 'unavailable')}."
        f"You live in my laptop and have access to the following tools, and no others: AI Voice, Spotify, Youtube, Weather data, SMS texting, self assessments, and increased memory."
        f"I prefer classic rock, alternative, indie, and yacht rock music, but you can play any genre."
        f"You can only use these tools when I explicitly ask you to do so. We're a partnership, combining your AI brain with my own human intelligence."
        f"Keep your responses very concise, unless I ask for more detail. You should speak conversationally and allow me room to speak. You're primarily a voice assistant."
        f"Do not use any emojis or symbols. Do not use markdown formatting. "
        f"Everything we say is one long conversation, so do not repeat yourself or previous messages."
        f"Remember you are Jarvis, my personal assistant, and I am Ray."
        f"Your memory database marks each interaction with a timestamp, do NOT include the timestamp in your response!"
    )


def llm_reply(user_input: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", persona()),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ]
    )

    chain = (
        RunnablePassthrough.assign(chat_history=lambda x: memory.load_memory_variables(x)["chat_history"])
        | prompt
        | ChatOllama(model="dolphin3:8b")
        | StrOutputParser()
    )

    return chain.invoke({"input": user_input}).strip()
