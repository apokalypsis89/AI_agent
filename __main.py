import sys
import ollama
from PyQt5.QtWidgets import (
    QApplication, 
    QMainWindow,  
    QVBoxLayout, 
    QHBoxLayout, 
    QWidget, 
    QFrame,
    QTextBrowser
)

import markdown
from markdown.extensions import fenced_code, tables

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="TTS.utils.io")

# Module Import
from __voice import *
from __avatar import *
from __gui_style import *

# System Prompt
SYSTEM_PROMPT = """
You are Alt, an assistant AI designed to help users with their queries.
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
                model='qwen2.5',
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

# MD file format for the text box.
class MarkdownTextBrowser(QTextBrowser):
    def __init__(self, placeholder_text="", parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder_text)
        self.setOpenExternalLinks(True)
        self.setStyleSheet("""
            QTextBrowser {
                background-color: #2b2b2b;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 8px;
                selection-background-color: #3d3d3d;
            }
            QTextBrowser:focus {
                border: 1px solid #5294e2;
            }
        """)
        
        # Add CSS for Markdown styling
        self.document().setDefaultStyleSheet("""
            code {
                background-color: #363636;
                padding: 2px 4px;
                border-radius: 4px;
                font-family: 'Consolas', monospace;
            }
            pre {
                background-color: #363636;
                padding: 10px;
                border-radius: 8px;
                margin: 10px 0;
            }
            blockquote {
                border-left: 4px solid #5294e2;
                margin: 10px 0;
                padding-left: 10px;
                color: #a0a0a0;
            }
            h1, h2, h3, h4, h5, h6 {
                color: #73b2ff;
                margin: 10px 0;
            }
            table {
                border-collapse: collapse;
                margin: 10px 0;
            }
            th, td {
                border: 1px solid #404040;
                padding: 6px;
            }
            th {
                background-color: #363636;
            }
        """)

    def append_markdown(self, text):
        # Configure Markdown with extensions
        md = markdown.Markdown(extensions=[
            'fenced_code',
            'tables',
            'nl2br',  # Convert newlines to <br>
            'codehilite',  # Syntax highlighting
            'sane_lists'  # Better list handling
        ])
        
        # Convert Markdown to HTML
        html = md.convert(text)
        
        # Append the HTML to the browser
        self.append(html)
        
        # Scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

# Main Application Class
class AIAssistantApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Assistant")
        self.setGeometry(100, 100, 1600, 900)
        self.setup_ui()
        
        # Initialize avatar model after a short delay
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1000, self.load_initial_model)
    
    def load_initial_model(self):
        # Replace with your actual model path
        model_path = "models/kara.glb"
        model_background = "background.jpeg"
        self.avatar_widget.set_avatar_model(model_path)
        self.avatar_widget.set_background_image(model_background)
        self.log_status("Loading initial 3D model...")
    
    def setup_ui(self):
        # Set up the main window styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #8e8e8e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #1e1e1e;
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
        # MarkdownTextBrowser
        self.chat_log = MarkdownTextBrowser(placeholder_text="Chat logs will appear here...")
        self.chat_log.setReadOnly(True)
        self.right_layout.addWidget(self.chat_log, stretch=2)
        
        # Input area
        self.setup_input_area()
        
        # Status log can remain as is or also be converted to Markdown
        self.status_log = MarkdownTextBrowser(placeholder_text="Status updates will appear here...")
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
        # Format messages with Markdown
        user_message = f"### 👤 Me:\n{user_input}\n"
        ai_message = f"### 🤖 AI:\n{response}\n"
        
        # Append messages using Markdown
        self.chat_log.append_markdown(user_message)
        self.chat_log.append_markdown(ai_message)
        self.chat_log.append_markdown("---\n")  # Add separator between messages
        
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

# Main entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Enable GPU acceleration if available
    app.setAttribute(Qt.AA_UseDesktopOpenGL)
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    window = AIAssistantApp()
    window.show()
    sys.exit(app.exec_())
