"""PocoFlow Voice Chat — continuous voice conversation with STT, LLM, and TTS.

Demonstrates: audio capture, speech-to-text, LLM chat, text-to-speech, looping flow.
"""

import os
import io
import threading
import numpy as np
import scipy.io.wavfile
import sounddevice as sd
import soundfile
import click
from openai import OpenAI
from pocoflow import Node, Flow, Store


# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------

def record_audio(sample_rate=44100, silence_threshold=0.01, silence_duration_ms=1000, max_duration_s=15):
    """Record audio with silence-based VAD. Returns (numpy_array, sample_rate) or (None, sample_rate)."""
    chunk_ms = 50
    chunk_frames = int(sample_rate * chunk_ms / 1000)
    min_silence_chunks = int(silence_duration_ms / chunk_ms)
    max_chunks = int(max_duration_s * 1000 / chunk_ms)

    recorded, is_recording, silence_count = [], False, 0
    pre_roll = []

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32") as stream:
        for i in range(max_chunks):
            chunk, _ = stream.read(chunk_frames)
            rms = np.sqrt(np.mean(chunk ** 2))

            if is_recording:
                recorded.append(chunk)
                if rms < silence_threshold:
                    silence_count += 1
                    if silence_count >= min_silence_chunks:
                        print("Silence detected, stopping recording.")
                        break
                else:
                    silence_count = 0
            else:
                pre_roll.append(chunk)
                if len(pre_roll) > 3:
                    pre_roll.pop(0)
                if rms > silence_threshold:
                    print("Speech detected, recording...")
                    is_recording = True
                    recorded.extend(pre_roll)
                    pre_roll.clear()

            if i == max_chunks - 1 and not is_recording:
                print("No speech detected.")
                return None, sample_rate

    if not recorded:
        return None, sample_rate

    audio = np.concatenate(recorded)
    print(f"Captured {len(audio) / sample_rate:.2f}s of audio.")
    return audio, sample_rate


def play_audio(audio_data, sample_rate):
    """Play numpy audio data through speakers."""
    sd.play(audio_data, sample_rate)
    sd.wait()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class CaptureAudioNode(Node):
    def exec(self, prep_result):
        print("\nListening for your query...")
        return record_audio()

    def post(self, store, prep_result, exec_result):
        audio, sr = exec_result
        if audio is None:
            print("Failed to capture audio.")
            return "end"
        store["audio_data"] = audio
        store["audio_sr"] = sr
        return "default"


class SpeechToTextNode(Node):
    def prep(self, store):
        return store.get("audio_data"), store.get("audio_sr"), store["_client"]

    def exec(self, prep_result):
        audio, sr, client = prep_result
        if audio is None:
            return None
        # Convert to WAV bytes
        buf = io.BytesIO()
        scipy.io.wavfile.write(buf, sr, audio)
        buf.name = "audio.wav"
        buf.seek(0)
        print("Transcribing speech...")
        transcript = client.audio.transcriptions.create(model="gpt-4o-transcribe", file=buf)
        return transcript.text

    def post(self, store, prep_result, exec_result):
        if not exec_result:
            print("STT returned no text.")
            return "end"
        print(f"You: {exec_result}")
        store.setdefault("chat_history", []).append({"role": "user", "content": exec_result})
        store["audio_data"] = None
        return "default"


class QueryLLMNode(Node):
    def prep(self, store):
        return store.get("chat_history", []), store["_client"], store.get("_model", "gpt-4o")

    def exec(self, prep_result):
        history, client, model = prep_result
        if not history:
            return None
        print("Thinking...")
        response = client.chat.completions.create(model=model, messages=history, temperature=0.7)
        return response.choices[0].message.content

    def post(self, store, prep_result, exec_result):
        if not exec_result:
            print("LLM returned no response.")
            return "end"
        print(f"Assistant: {exec_result}")
        store["chat_history"].append({"role": "assistant", "content": exec_result})
        return "default"


class TextToSpeechNode(Node):
    def prep(self, store):
        history = store.get("chat_history", [])
        if history and history[-1].get("role") == "assistant":
            return history[-1]["content"], store["_client"]
        return None, None

    def exec(self, prep_result):
        text, client = prep_result
        if not text:
            return None
        print("Generating speech...")
        response = client.audio.speech.create(model="gpt-4o-mini-tts", voice="alloy", input=text, response_format="mp3")
        return response.content

    def post(self, store, prep_result, exec_result):
        if exec_result:
            try:
                audio, sr = soundfile.read(io.BytesIO(exec_result))
                play_audio(audio, sr)
            except Exception as e:
                print(f"Error playing audio: {e}")
        return "next_turn"


@click.command()
@click.option("--model", default="gpt-4o", help="OpenAI model for chat")
def main(model):
    """Voice chat: speak, get LLM response, hear it spoken back."""
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    capture = CaptureAudioNode()
    stt = SpeechToTextNode()
    llm = QueryLLMNode()
    tts = TextToSpeechNode()

    capture.then("default", stt)
    stt.then("default", llm)
    llm.then("default", tts)
    tts.then("next_turn", capture)  # loop back

    store = Store(
        data={"chat_history": [], "_client": client, "_model": model},
        name="voice_chat",
    )

    print("=== PocoFlow Voice Chat ===")
    print("Speak after 'Listening...' appears. Press Ctrl+C to stop.\n")

    flow = Flow(start=capture)
    flow.run(store)


if __name__ == "__main__":
    main()
