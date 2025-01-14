import sys
import os
import ollama
from PyQt5.QtWidgets import (
    QApplication, 
    QMainWindow, 
    QPushButton, 
    QVBoxLayout, 
    QHBoxLayout, 
    QWidget, 
    QLineEdit, 
    QTextEdit,
    QFrame
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QThread, pyqtSignal, QObject, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="TTS.utils.io")

# Module Import
from __voice import *
from __avatar import *


# System Prompt
SYSTEM_PROMPT = """
You are Alt, an assistant designed to provide actionable advice and help solve complex problems creatively. 
Your responses should feel human-like, explanatory, practical, and engaging, avoiding generic suggestions. 
Answer in concise, professional paragraphs with bullet points only if it is necessary. 
Use clear questions and answer to understand the motives behind a problem and brainstorm with solutions.
"""

# Ollama Worker Class (unchanged)
class OllamaWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    
    def __init__(self, prompt, context=""):
        super().__init__()
        self.prompt = prompt
        self.context = context
        
    def run(self):
        try:
            response = ollama.chat(
                model='llama3.2',
                messages=[
                    {
                        'role': 'system',
                        'content': SYSTEM_PROMPT
                    },
                    {
                        'role': 'user',
                        'content': self.context + "\n" + self.prompt
                    }
                ]
            )
            self.finished.emit(response['message']['content'])
        except Exception as e:
            self.error.emit(str(e))

# Main Application Class
class AIAssistantApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Assistant")
        self.setGeometry(100, 100, 1200, 800)
        self.setup_ui()
        
        # Initialize avatar model after a short delay
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1000, self.load_initial_model)
    
    def load_initial_model(self):
        # Replace with your actual model path
        model_path = "models/avatar_3.glb"
        self.avatar_widget.set_avatar_model(model_path)
        self.log_status("Loading initial 3D model...")
    
    def setup_ui(self):
        # Set up the main window styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)
        
        # Initialize media player
        self.media_player = QMediaPlayer()
        
        # Create central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        self.main_layout.setSpacing(20)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Set up left panel with avatar
        self.setup_left_panel()
        
        # Set up right panel with chat interface
        self.setup_right_panel()
        
        self.central_widget.setLayout(self.main_layout)
        
        # Initialize workers
        self.voice_worker = None
        self.ollama_worker = None
        
        # Initialize conversation context
        self.conversation_context = ""
        
        # Set application font
        app_font = QFont("Segoe UI", 10)
        QApplication.setFont(app_font)

    def setup_left_panel(self):
        self.left_panel = QFrame()
        self.left_panel.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        self.left_layout = QVBoxLayout()
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create and add avatar widget
        self.avatar_widget = AvatarWidget()
        self.left_layout.addWidget(self.avatar_widget)
        self.left_panel.setLayout(self.left_layout)
        self.main_layout.addWidget(self.left_panel, stretch=1)

    def setup_right_panel(self):
        self.right_panel = QFrame()
        self.right_panel.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(16)
        
        # Add chat components
        self.setup_chat_components()
        
        self.right_panel.setLayout(self.right_layout)
        self.main_layout.addWidget(self.right_panel, stretch=2)

    def setup_chat_components(self):
        # Chat log
        self.chat_log = StyledTextEdit(placeholder_text="Chat logs will appear here...")
        self.chat_log.setReadOnly(True)
        self.right_layout.addWidget(self.chat_log, stretch=2)
        
        # Input area
        self.setup_input_area()
        
        # Status log
        self.status_log = StyledTextEdit(placeholder_text="Status updates will appear here...")
        self.status_log.setReadOnly(True)
        self.status_log.setMaximumHeight(150)
        self.right_layout.addWidget(self.status_log)

    def setup_input_area(self):
        self.input_frame = QFrame()
        self.input_frame.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        self.input_layout = QHBoxLayout()
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setSpacing(8)
        
        self.input_bar = StyledLineEdit()
        self.input_bar.setPlaceholderText("Type your query here...")
        self.input_bar.returnPressed.connect(self.process_text_input)
        
        self.submit_button = StyledButton("Submit")
        self.submit_button.clicked.connect(self.process_text_input)
        self.submit_button.setFixedWidth(100)
        
        self.input_layout.addWidget(self.input_bar)
        self.input_layout.addWidget(self.submit_button)
        self.input_frame.setLayout(self.input_layout)
        self.right_layout.addWidget(self.input_frame)

    # Keep all other methods from your original implementation
    def log_status(self, message):
        current_text = self.status_log.toPlainText()
        if len(current_text.split('\n')) > 100:
            lines = current_text.split('\n')[50:]
            self.status_log.setPlainText('\n'.join(lines))
        
        self.status_log.append(f"[{self.get_timestamp()}] {message}")
        scrollbar = self.status_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def get_timestamp(self):
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
        
    def append_chat_log(self, user_input, response):
        self.chat_log.append(f'<span style="color: #5294e2;">You:</span> {user_input}')
        self.chat_log.append(f'<span style="color: #73b2ff;">AI:</span> {response}')
        self.chat_log.append("")
        scrollbar = self.chat_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def process_text_input(self):
        text = self.input_bar.text().strip()
        if text:
            self.submit_button.setEnabled(False)
            self.input_bar.clear()
            self.log_status("Generating response...")
            
            self.ollama_worker = OllamaWorker(text, self.conversation_context)
            self.ollama_worker.finished.connect(lambda response: self.handle_ollama_response(text, response))
            self.ollama_worker.error.connect(self.handle_ollama_error)
            self.ollama_worker.start()
        else:
            self.log_status("Error: Text input is empty. Please type something.")
            
    def handle_ollama_response(self, user_input, response):
        # Update conversation context
        self.conversation_context += f"\nUser: {user_input}\nAssistant: {response}"
        # Keep only last few exchanges to prevent context from growing too large
        self.conversation_context = "\n".join(self.conversation_context.split("\n")[-10:])
        
        self.append_chat_log(user_input, response)
        self.respond(response)
        self.submit_button.setEnabled(True)
        
    def handle_ollama_error(self, error_message):
        self.log_status(f"Error generating response: {error_message}")
        self.submit_button.setEnabled(True)
            
    def respond(self, response):
        self.log_status("Starting voice generation...")
        
        self.voice_worker = VoiceWorker(response)
        self.voice_worker.finished.connect(self.handle_voice_ready)
        self.voice_worker.error.connect(self.handle_voice_error)
        self.voice_worker.progress.connect(self.handle_progress)
        self.voice_worker.start()
        
    def handle_progress(self, value):
        self.log_status(f"Voice generation progress: {value}%")
        
    def handle_voice_ready(self, audio_path):
        self.log_status("Voice generation complete. Playing audio...")
        url = QUrl.fromLocalFile(audio_path)
        content = QMediaContent(url)
        self.media_player.setMedia(content)
        self.media_player.play()
        
    def handle_voice_error(self, error_message):
        self.log_status(f"Error: Voice processing failed - {error_message}")

# Styled Component Classes
class StyledTextEdit(QTextEdit):
    def __init__(self, placeholder_text="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPlaceholderText(placeholder_text)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #404040;
            }
            QScrollBar:vertical {
                border: none;
                background: #2b2b2b;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #404040;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

class StyledLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #404040;
            }
            QLineEdit:focus {
                border: 1px solid #5294e2;
            }
        """)

class StyledButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("""
            QPushButton {
                background-color: #5294e2;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #73b2ff;
            }
            QPushButton:pressed {
                background-color: #3d70b2;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
        """)

# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Enable GPU acceleration if available
    app.setAttribute(Qt.AA_UseDesktopOpenGL)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    window = AIAssistantApp()
    window.show()
    sys.exit(app.exec_())