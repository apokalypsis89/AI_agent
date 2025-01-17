import sys
from pathlib import Path
import tempfile
import logging
import numpy as np
import librosa
import speech_recognition as sr
from pydub import AudioSegment
import pyttsx3
from PyQt5.QtCore import QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication
import queue
import threading
import warnings
import re
warnings.filterwarnings("ignore")

class VoiceHandler(QObject):
    """Handles speech processing with pyttsx3 and voice effects"""
    
    speech_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, language='en'):
        super().__init__()
        self.language = language
        self.logger = logging.getLogger(__name__)
        self.temp_dir = Path(tempfile.gettempdir()) / 'ai_assistant_speech'
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialize pyttsx3
        self.engine = pyttsx3.init()
        self.engine.setProperty('voice', pyttsx3.init().getProperty('voices')[2].id) # its MS hazel don't hate me for not using jenny but she is far slower.
        self.engine.setProperty('rate', 160)
        self.engine.setProperty('volume', 0.8)
        
        # Initialize queue for async processing
        self.audio_queue = queue.Queue()
        self.cache = {}
        self._start_queue_processor()

    def clean_markdown(self, text: str) -> str:
        """Remove markdown formatting from text"""
        # Remove bold/italic markers
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove **bold**
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove *italic*
        text = re.sub(r'__(.*?)__', r'\1', text)      # Remove __bold__
        text = re.sub(r'_(.*?)_', r'\1', text)        # Remove _italic_
        # Remove code markers
        text = re.sub(r'`(.*?)`', r'\1', text)        # Remove `code`
        # Remove block code markers
        text = re.sub(r'```.*?\n(.*?)```', r'\1', text, flags=re.DOTALL)
        # Remove markdown links
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)  # Convert [text](url) to just text
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove hashtags used for headers while keeping the text
        text = re.sub(r'#{1,6}\s+', '', text)
        # Remove bullet points to natural speech
        text = re.sub(r'^\s*[-*+]\s+', ' ', text, flags=re.MULTILINE)
        # Remove numbered lists to natural speech
        text = re.sub(r'^\s*\d+\.\s+', ' ', text, flags=re.MULTILINE)
        # Remove excessive newlines
        text = re.sub(r'\n\s*\n', '\n', text)
        # Remove any remaining special characters that might interfere with TTS
        text = re.sub(r'[~\[\]{}|<>]', '', text)

        return text.strip()

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
        for i in range(2):
            delay = int((i + 1) * delay_ms)
            echo = original._spawn(original.raw_data)
            echo = echo - (decay * (i + 1))
            reverb_sound = reverb_sound.overlay(echo, position=delay)
        return reverb_sound
    
    def apply_voice_effects(self, audio_path: Path) -> Path:
        """Apply voice effects to audio"""
        audio = AudioSegment.from_wav(str(audio_path))
        
        # Apply effects in sequence
        segments = []
        chunk_size = 500
        
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i:i+chunk_size]
            pitch_shift_amount = np.sin(i / 100) * 0.1
            modified_chunk = self.pitch_shift(chunk, pitch_shift_amount)
            segments.append(modified_chunk)
        
        modified = sum(segments[1:], segments[0])
        modified = self.add_reverb(modified, delay_ms=20, decay=0.05)
        modified = modified.high_pass_filter(1000)
        
        output_path = audio_path.parent / f"processed_{audio_path.name}"
        modified.export(str(output_path), format="wav")
        
        return output_path
    
    def _start_queue_processor(self):
        """Start the background thread for processing TTS requests"""
        def process_queue():
            while True:
                try:
                    text = self.audio_queue.get()
                    if text is None:
                        break
                    
                    # Clean markdown before TTS processing
                    cleaned_text = self.clean_markdown(text)
                    
                    # Generate base TTS
                    temp_path = self._generate_tts(cleaned_text)
                    # Apply voice effects
                    output_path = self.apply_voice_effects(temp_path)
                    self.speech_ready.emit(str(output_path))
                    
                except Exception as e:
                    self.error_occurred.emit(str(e))
                finally:
                    self.audio_queue.task_done()
        
        self.queue_thread = threading.Thread(target=process_queue, daemon=True)
        self.queue_thread.start()
    
    def _generate_tts(self, text: str) -> Path:
        """Generate TTS audio file using pyttsx3"""
        cache_key = hash(text)
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        output_path = self.temp_dir / f"tts_{cache_key}.wav"
        self.engine.save_to_file(text, str(output_path))
        self.engine.runAndWait()
        
        self.cache[cache_key] = output_path
        return output_path
    
    def generate_speech(self, text: str):
        """Queue text for TTS generation"""
        self.audio_queue.put(text)
    
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
    
    def cleanup(self):
        """Clean up resources"""
        self.audio_queue.put(None)
        self.queue_thread.join()
        self.engine.stop()

# Rest of the code remains the same...

class VoiceWorker(QThread):
    """Worker thread for voice processing"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, text: str):
        super().__init__()
        self.text = text
        self.voice_handler = None
    
    def run(self):
        try:
            self.progress.emit(10)
            self.voice_handler = VoiceHandler()
            self.voice_handler.speech_ready.connect(self._on_speech_ready)
            self.voice_handler.error_occurred.connect(self._on_error)
            
            self.progress.emit(20)
            self.voice_handler.generate_speech(self.text)
            
            self.exec_()
            
        except Exception as e:
            self.error.emit(str(e))
    
    def _on_speech_ready(self, path):
        self.progress.emit(100)
        self.finished.emit(path)
        self.quit()
    
    def _on_error(self, error_msg):
        self.error.emit(error_msg)
        self.quit()
    
    def cleanup(self):
        if self.voice_handler:
            self.voice_handler.cleanup()

# Example usage
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    def on_finished(path):
        print(f"Audio saved to: {path}")
        app.quit()
    
    def on_error(error):
        print(f"Error: {error}")
        app.quit()
    
    text = "Hello, this is a test of the voice generation system."
    worker = VoiceWorker(text)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    worker.start()
    
    sys.exit(app.exec_())
