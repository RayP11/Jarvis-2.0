from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferMemory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from recognize import listen_for_command
from new_voice import speak_text
from spotify_functions import play_music, play_song
import os
import time
from datetime import datetime
from text_reminders import send_message_with_audio, check_for_sms_replies, send_message
from file_output import generate_audio_mp3

# Initialize AI model and memory
model = ChatOllama(model="gemma3:4b")
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

now = datetime.now()
today_str = now.strftime("%A, %B %d, %Y at %I:%M %p")

# Persona and prompt
persona = f"""
You are Friday, my personal assistant. I am Ray, your creator. Your traits: professional, efficient, and subtly witty, sarcastic, but always respectful and devoted to your creator.
You are an LLM combined with the functions I've built for you. Current functions: play music on spotify.
Your current functions: Assist with any questions I have, play music, provide notes, provide reminders, and ensure I'm taking care of myself daily.
my music taste includes a mix of pop, rock, alt, and rap.
Don't use symbols in your responses.
Keep responses short and conversational.
Refer to me as Ray or Boss.
Only use sentences (no bullet points or lists).
today is {today_str}. I want you to remind me to take care of myself daily.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", persona),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

# Chain to generate response
conversation_chain = (
    RunnablePassthrough.assign(
        chat_history=lambda x: memory.load_memory_variables(x)["chat_history"]
    )
    | prompt
    | model
    | StrOutputParser()
)

# Conversation history for optional use
conversation_history = []

# Helpers
def update_history(user_input, ai_output):
    conversation_history.append({
        "user": user_input,
        "ai": ai_output,
    })

def ai_response(user_input):
    """Normal response with memory tracking"""
    response = conversation_chain.invoke({"input": user_input}).strip()

    memory.save_context(
        {"input": user_input},
        {"output": response}
    )

    update_history(user_input, response)
    return response

def separate_response(user_input):
    """Response without memory tracking"""
    response = conversation_chain.invoke({"input": user_input}).strip()
    update_history(user_input, response)
    return response

def handle_command(user_input, mode):
    """Handle command inputs like switching modes or playing music."""
    input_lower = user_input.lower()

    if input_lower == "quit":
        print("Friday: Goodbye!")
        return "exit"
    elif input_lower == "switch to voice":
        print("🔊 Switched to VOICE mode.")
        return "voice"
    elif input_lower == "switch to text":
        print("⌨️ Switched to TEXT mode.")
        return "text"
    elif input_lower == "switch to headphone":
        print("🎧 Switched to HEADPHONE mode.")
        return "headphone"
    elif input_lower == "switch to voice texting":
        print("📱 Switched to VOICE TEXTING mode.")
        return "voice_texting"
    elif input_lower == "switch to texting":
        print("📱 Switched to TEXTING mode.")
        return "texting"
    elif "play " in input_lower:
        play_music(user_input)
        return "skip_response"
    elif "put something on" in input_lower or "next song" in input_lower:
        song_name = ai_response(f"Spotify tool triggered: pick a song for me, don't say the artist name or anything else, output just the song name and ONLY the song name: {user_input}")
        os.system('spotify')
        time.sleep(3)
        play_song(song_name)
        speak_text(f"Playing {song_name} on Spotify")
        return "skip_response"

    return None

# Main Chat Loop
def chat():
    mode = "text"
    print("Friday AI initialized.")
    print("Type or say 'switch to voice' or 'switch to text' to change modes.")
    print("Say or type 'quit' to exit.\n")

    while True:
        try:
            if mode == "voice":
                user_input = listen_for_command()
                if not user_input:
                    continue
                print(f"\nYou (voice): {user_input}")
            elif mode == "texting":
                print("📩 Checking for new text replies...")
                user_input = check_for_sms_replies("4438964231@vzwpix.com") 
                if not user_input:
                    continue
                print(f"\nYou (text): {user_input}")
            elif mode == "voice_texting":
                print("📩 Checking for new text replies...")
                user_input = check_for_sms_replies("4438964231@vzwpix.com")
                if not user_input:
                    continue
            else:
                user_input = input("You (text): ").strip()

            
        

            if not user_input:
                continue

            # Handle special commands
            command_result = handle_command(user_input, mode)
            if command_result == "exit":
                break
            elif command_result in ["voice", "text", "headphone"]:
                mode = command_result
                continue
            elif command_result == "skip_response":
                continue  # Skip normal AI response
            elif command_result == "texting":
                mode = "texting"
                continue
            elif command_result == "voice_texting":
                mode = "voice_texting"
                continue

            # Normal AI chat
            response = ai_response(user_input)
            if mode == "texting":
                send_message(response)
                time.sleep(5)
            elif mode == "voice_texting":
                audio_path = generate_audio_mp3(response)
                if audio_path:
                    send_message_with_audio("Friday: ", audio_path)
                    time.sleep(5)
            print(f"\nFriday: {response}\n")

            if mode in ["voice", "headphone"]:
                speak_text(response)

        except KeyboardInterrupt:
            print("\nFriday: Session ended.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue

if __name__ == "__main__":
    chat()
