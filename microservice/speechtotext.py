from faster_whisper import WhisperModel
import tempfile
import os
from fastapi import UploadFile, File, Query
import speech_recognition as sr
import re
from word2number import w2n
from pydub import AudioSegment
import os

def clean_transcription(text):
   
    # Step 1: Remove unwanted punctuation (optional if needed)
    text = re.sub(r"[-.,:'\"]", "", text)
    

    # 3. Convert word numbers to digits
    words = text.split()
    new_words = []
    for word in words:
        try:
            num = w2n.word_to_num(word)
            new_words.append(str(num))
        except ValueError:
            new_words.append(word)
    text = " ".join(new_words)

    # 4. Remove spaces between digits (e.g., "0 3 0 0" → "0300")
    text = re.sub(r'(?<=\d) (?=\d)', '', text)
    
    return text

model = WhisperModel("base", compute_type="int8")

async def transcribe(file: UploadFile = File(...), audio: str = Query("en", description="Language hint for transcription")):
    try:
        # Save uploaded audio
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as temp_audio:
            contents = await file.read()
            temp_audio.write(contents)
            input_path = temp_audio.name

        if audio == "en":
            segments, _ = model.transcribe(input_path, beam_size=2, language="en")
            transcription = " ".join([seg.text for seg in segments])
            os.remove(input_path)
            return clean_transcription(transcription.strip())
            

        else:
            return clean_transcription(speech_to_text(audio_file=input_path))
            

    except Exception as e:
        return {"error": str(e)}


def speech_to_text(audio_file: str, lang: str = 'ur-pk') -> str:
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True

        wav_path = audio_file.replace('.webm', '.wav')
        success = convert_webm_to_wav(input_path=audio_file, output_path=wav_path)
        if not success:
            return "Audio conversion failed"
        
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        
        try:
            text = recognizer.recognize_google(audio_data, language=lang)
            os.remove(wav_path)  # Clean up
            return text
        except sr.UnknownValueError:
            return "Could not understand the audio"
        except sr.RequestError as e:
            return f"Could not request results; {e}"

    

def convert_webm_to_wav(input_path, output_path):
    try:
        print("📂 File exists?", os.path.exists(input_path))
        print("📄 File size:", os.path.getsize(input_path), "bytes")
        print("📎 File extension:", os.path.splitext(input_path)[1])

        # Decode WebM properly
        audio = AudioSegment.from_file(input_path, format="webm")
        
        # Export to WAV
        audio.export(output_path, format="wav")
        print("✅ Conversion successful:", output_path)
        return True
    except Exception as e:
        print("❌ Conversion failed:", str(e))
        return False


