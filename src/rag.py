from datetime import datetime
from langchain_chroma import Chroma
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain.schema.output_parser import StrOutputParser
from langchain_community.document_loaders import (
    PyMuPDFLoader, TextLoader, CSVLoader, Docx2txtLoader, UnstructuredPowerPointLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.runnable import RunnablePassthrough
from langchain.prompts import PromptTemplate, ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain_community.vectorstores.utils import filter_complex_metadata
import os
import shutil
import cv2
import pytesseract
from PIL import Image
from moviepy import VideoFileClip
import whisper
import threading
import time
from langchain.schema.runnable import RunnableMap

from db import memory as global_memory 


def persona() -> str:
    local_time = datetime.now().strftime("%A, %B %d %Y %I:%M %p")
    return (
        f"Call me sir. Today is {local_time}. "
        f"You live in my laptop and have access to the following tools, and no others: AI Voice, Spotify, Youtube, Weather data, SMS texting, self assessments, and increased memory."
        f"I prefer classic rock, alternative, indie, and yacht rock music, but you can play any genre."
        f"You can only use these tools when I explicitly ask you to do so. We're a partnership, combining your AI brain with my own human intelligence."
        f"Keep your responses very concise, unless I ask for more detail. You should speak conversationally and allow me room to speak. You're primarily a voice assistant."
        f"Do not use any emojis or symbols. Do not use markdown formatting. "
        f"Everything we say is one long conversation, so do not repeat yourself or previous messages."
        f"Remember I am Ray, and you are Jarvis."
        f"Your memory database marks each interaction with a timestamp, do NOT include the timestamp in your response!"
    )

class ChatDocument:
    def __init__(self, uploads_dir):
        self.uploads_dir = uploads_dir
        self.model = ChatOllama(model="jarvis")
        self.text_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " "],
            chunk_size=2000,
            chunk_overlap=200,
        )
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")
        self.vector_store = None
        self.retriever = None
        self.chain = None
        self._watched_files = set()
        self._watching_thread = None
        self._watch_stop_flag = False

        self._initialize_vector_store()

        local_time = datetime.now().strftime("%A, %B %d %Y %I:%M %p")
        self.prompt = PromptTemplate.from_template(
            """
            You are Jarvis, I am Ray.

            - Always refer to me as "sir."
            - Today is {local_time}.
            - You live inside my laptop and have access to the following tools only when explicitly asked: AI Voice, Spotify, YouTube, Weather data, SMS texting, self assessments, and increased memory.
            - I prefer classic rock, alternative, indie, and yacht rock music — but you may suggest any genre when prompted.
            - You and I are partners: combine your AI capabilities with my human intelligence.
            - You are augmented with RAG (Retrieval-Augmented Generation) capabilities, allowing you to access and summarize information from documents in your database.
            
            You are a voice assistant, so speak conversationally and allow me room to speak. Keep responses concise unless I ask for more detail.
            Do not use emojis, symbols, or markdown formatting. Everything we say is one long conversation, so no need to repeat yourself or previous messages.
            Do not include timestamps in your responses.

            Remember: I am Ray, and you are Jarvis.

            Chat History: {chat_history}
            Context: {context}
            Question: {question}
            Answer:
            """
        ).partial(local_time=local_time)

    def _initialize_vector_store(self):
        if self.vector_store:
            self.vector_store = None
        if os.path.exists("chroma_db"):
            shutil.rmtree("chroma_db")
        self.vector_store = Chroma(persist_directory="chroma_db", embedding_function=self.embeddings)
        self.retriever = self.vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 100, "score_threshold": 0.25},
        )

    def _load_and_split_documents(self, file_path: str):
        file_extension = file_path.split(".")[-1].lower()
        docs = []
        try:
            if file_extension == "pdf":
                loader = PyMuPDFLoader(file_path)
            elif file_extension == "txt":
                loader = TextLoader(file_path)
            elif file_extension == "csv":
                loader = CSVLoader(file_path)
            elif file_extension == "docx":
                loader = Docx2txtLoader(file_path)
            elif file_extension == "pptx":
                loader = UnstructuredPowerPointLoader(file_path)
            elif file_extension in ["mp4", "avi", "mov"]:
                text = self._analyze_video(file_path)
                from langchain.schema import Document
                docs = [Document(page_content=text, metadata={"source": file_path, "type": "video"})]
                chunks = self.text_splitter.split_documents(docs)
                return filter_complex_metadata(chunks)
            else:
                print(f"Unsupported file format: {file_extension}")
                return []

            docs = loader.load()
            for doc in docs:
                doc.metadata["type"] = file_extension
            chunks = self.text_splitter.split_documents(docs)
            return filter_complex_metadata(chunks)
        except Exception as e:
            print(f"Error loading file {file_path}: {e}")
            return []

    def _extract_video_text(self, video_path: str, frame_interval: int = 10):
        cap = cv2.VideoCapture(video_path)
        frame_count = 0
        extracted_text = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % frame_interval == 0:
                pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                text = pytesseract.image_to_string(pil_image)
                extracted_text.append(text)
            frame_count += 1

        cap.release()
        return "\n".join(extracted_text)

    def _extract_video_audio(self, video_path, output_audio_path):
        video = VideoFileClip(video_path)
        audio = video.audio
        audio.write_audiofile(output_audio_path, codec='pcm_s16le')
        video.close()
        audio.close()

    def audio_to_text(self, audio_path):
        model = whisper.load_model("small")
        result = model.transcribe(audio_path)
        return result["text"].strip() if result["text"] else "could not understand audio"

    def _analyze_video(self, video_path: str):
        frames_text = self._extract_video_text(video_path)
        self._extract_video_audio(video_path, "extracted_audio.wav")
        audio_text = self.audio_to_text("extracted_audio.wav")
        return f"Extracted Text from Frames: {frames_text} Extracted Audio Text: {audio_text}"

    def ingest(self, file_path: str):
        if not os.path.isfile(file_path):
            raise ValueError("File path must point to a valid document.")
        chunks = self._load_and_split_documents(file_path)
        if self.vector_store:
            self.vector_store.add_documents(chunks)
        else:
            self.vector_store = Chroma.from_documents(documents=chunks, embedding=self.embeddings, persist_directory="chroma_db")
        self.retriever = self.vector_store.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={"k": 100, "score_threshold": 0.3},
        )
        self.chain = (
            RunnableMap({
                "question": lambda x: x,
                "chat_history": lambda x: global_memory.load_memory_variables(x)["chat_history"],
                "context": self.retriever,
            })
            | self.prompt
            | self.model
            | StrOutputParser()
        )

        print(f"Ingested document: {file_path}")

    def llm_reply(self, user_input: str) -> str:
        if self.chain:
            try:
                global_memory.chat_memory.add_user_message(user_input)
                response = self.chain.invoke(user_input)
                global_memory.chat_memory.add_ai_message(response)
                return response.strip()
            except Exception as e:
                print(f"RAG failed: {e} — falling back to base model.")

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", persona()),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )
        fallback_chain = (
            RunnablePassthrough.assign(chat_history=lambda x: global_memory.load_memory_variables(x)["chat_history"])
            | prompt
            | ChatOllama(model="jarvis")
            | StrOutputParser()
        )
        return fallback_chain.invoke({"input": user_input}).strip()

    def clear(self):
        self.vector_store = None
        self.retriever = None
        self.chain = None
        global_memory.clear()
        print("State cleared.")

    def watch_folder(self, interval=5):
        if self._watching_thread and self._watching_thread.is_alive():
            print("Already watching folder.")
            return

        def _watch_loop():
            print(f"Started watching folder: {self.uploads_dir}")
            while not self._watch_stop_flag:
                try:
                    for filename in os.listdir(self.uploads_dir):
                        filepath = os.path.join(self.uploads_dir, filename)
                        if os.path.isfile(filepath) and filepath not in self._watched_files:
                            print(f"New file detected: {filepath}")
                            self.ingest(filepath)
                            self._watched_files.add(filepath)
                except Exception as e:
                    print(f"Watch error: {e}")
                time.sleep(interval)

        self._watch_stop_flag = False
        self._watching_thread = threading.Thread(target=_watch_loop, daemon=True)
        self._watching_thread.start()

    def stop_watching_folder(self):
        self._watch_stop_flag = True
        if self._watching_thread:
            self._watching_thread.join()
            print("Stopped watching folder.")
