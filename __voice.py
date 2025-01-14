import asyncio
from pathlib import Path
import tempfile
import logging
import numpy as np
import librosa
import speech_recognition as sr
from pydub import AudioSegment
from TTS.api import TTS

from PyQt5.QtCore import QThread, pyqtSignal

import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="TTS.utils.io")

class VoiceHandler:
    """Handles speech processing with custom voice model"""
    
    def __init__(self, language='en'):
        self.language = language
        self.logger = logging.getLogger(__name__)
        self.temp_dir = Path(tempfile.gettempdir()) / 'ai_assistant_speech'
        self.temp_dir.mkdir(exist_ok=True)
        self.tts_model = TTS("tts_models/en/jenny/jenny")  # Initialize once
        
    # Remove async initialization as the model is initialized once in __init__
    
    def pitch_shift(self, audio_segment, octaves):
        """Apply pitch shifting to audio"""
        samples = np.array(audio_segment.get_array_of_samples()).astype(np.float32)
        sample_rate = audio_segment.frame_rate
        
        shifted = librosa.effects.pitch_shift(
            y=samples,
            sr=sample_rate,
            n_steps=12 * octaves
        )
        
        return AudioSegment(
            shifted.astype(np.int16).tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1
        )
    
    def add_reverb(self, audio, delay_ms, decay):
        """Add reverb effect to audio"""
        original = audio
        reverb_sound = original.fade_out(int(delay_ms))
        for i in range(2):  # Reduce the number of reverb iterations
            delay = int((i + 1) * delay_ms)
            echo = original._spawn(original.raw_data)
            echo = echo - (decay * (i + 1))
            reverb_sound = reverb_sound.overlay(echo, position=delay)
        return reverb_sound
    
    async def process_voice_response(self, text: str) -> Path:
        """Process text to speech with custom voice effects"""
        try:
            temp_raw = self.temp_dir / f"temp_{hash(text)}.wav"
            output_path = self.temp_dir / f"processed_{hash(text)}.wav"
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.tts_model.tts_to_file(text=text, file_path=str(temp_raw))
            )
            
            audio = AudioSegment.from_wav(str(temp_raw))
            segments = []
            chunk_size = 500  # Increase chunk size to reduce processing iterations
            
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i+chunk_size]
                pitch_shift_amount = np.sin(i / 100) * 0.1
                modified_chunk = self.pitch_shift(chunk, pitch_shift_amount)
                segments.append(modified_chunk)
            
            modified = sum(segments[1:], segments[0])
            modified = self.add_reverb(modified, delay_ms=20, decay=0.05)  # Adjust reverb parameters
            modified = modified.high_pass_filter(1000)
            
            modified.export(str(output_path), format="wav")
            temp_raw.unlink(missing_ok=True)
            
            return output_path
            
        except Exception as e:
            self.logger.error(f"Voice processing error: {e}")
            raise
        
    def record_speech(self):
        """Record speech and convert it to text"""
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            self.logger.info("Listening...")
            audio = recognizer.listen(source)
            try:
                text = recognizer.recognize_google(audio)
                self.logger.info(f"Recognized text: {text}")
                return text
            except sr.UnknownValueError:
                self.logger.error("Google Speech Recognition could not understand audio")
                return ""
            except sr.RequestError as e:
                self.logger.error(f"Could not request results from Google Speech Recognition service; {e}")
                return ""

class VoiceWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, text):
        super().__init__()
        self.text = text
        self.voice_handler = VoiceHandler()
        
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Process in chunks to update progress
            self.progress.emit(20)  # Model initialization
            audio_path = loop.run_until_complete(
                self.voice_handler.process_voice_response(self.text)
            )
            self.progress.emit(100)
            
            self.finished.emit(str(audio_path))
            loop.close()
            
        except Exception as e:
            self.error.emit(str(e))
