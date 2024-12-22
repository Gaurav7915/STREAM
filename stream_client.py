from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLabel,
QGridLayout, QVBoxLayout, QPushButton)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
import requests
from requests.exceptions import RequestException
import threading
import sys

# Constants
BASE_GREEN_TIME = 10  # Base time of 10 seconds for each signal
MAX_GREEN_TIME = 30   # Cap green time at 90 seconds
VEHICLES_PER_SECOND = 2  # Assuming 2 vehicles pass per second
BUFFER_TIME = 5
API_BASE_URL = "http://192.168.61.28:5000"  # Change to your Raspberry Pi's IP

class ImageDropZone(QLabel):
    image_dropped = pyqtSignal(str, int)

    def __init__(self, signal_id):
        super().__init__()
        self.signal_id = signal_id
        self.setMinimumSize(200, 200)
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(False)
        self.updateStyle("inactive")

    def updateStyle(self, state):
        styles = {
            "inactive": ("Drop disabled", "#444", "#222", "#666"),
            "upload": ("Drop image here", "#cc0000", "#333", "#fff"),
            "active": ("Signal active", "#00cc00", "#333", "#fff"),
            "buffer": ("Preparing next", "#ffcc00", "#333", "#fff")
        }
        text, border_color, bg_color, text_color = styles[state]
        self.setStyleSheet(f"""
            QLabel {{
                border: 2px solid {border_color};
                border-radius: 5px;
                background-color: {bg_color};
                color: {text_color};
                font-size: 14px;
            }}
        """)
        self.setText(f"Signal {self.signal_id + 1}\n{text}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and self.acceptDrops():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls() and self.acceptDrops():
            file_path = event.mimeData().urls()[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    pixmap = QPixmap(file_path)
                    scaled_pixmap = pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.setPixmap(scaled_pixmap)
                    self.image_dropped.emit(file_path, self.signal_id)
                except Exception as e:
                    print(f"Error loading image: {e}")
            event.accept()
        else:
            event.ignore()

class TrafficSignal(QWidget):
    def __init__(self, signal_id):
        super().__init__()
        self.signal_id = signal_id
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        
        self.drop_zone = ImageDropZone(self.signal_id)
        self.timer_label = QLabel("0")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet("""
            QLabel {
                border: 2px solid #666;
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
                background-color: #333;
                color: white;
                min-width: 50px;
                min-height: 50px;
            }
        """)
        
        layout.addWidget(self.drop_zone)
        layout.addWidget(self.timer_label)
        self.setLayout(layout)

    def update_timer(self, time, state):
        self.timer_label.setText(str(time))
        colors = {
            "red": "#cc0000",
            "green": "#00cc00",
            "yellow": "#ffcc00",
            "inactive": "#333"
        }
        self.timer_label.setStyleSheet(f"""
            QLabel {{
                border: 2px solid #666;
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
                background-color: {colors[state]};
                color: white;
                min-width: 50px;
                min-height: 50px;
            }}
        """)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("STREAM - Traffic Management System")
        self.setStyleSheet("background-color: #1a1a1a;")

        self.signals = []
        self.current_signal = 0
        self.next_signal = 1
        self.current_time = BASE_GREEN_TIME
        self.new_green_time = None
        self.is_running = False
        
        self.setup_ui()
        self.setup_timer()
        
        # Start the system
        self.start_system()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        
        # Create traffic signals
        for i in range(4):
            signal = TrafficSignal(i)
            signal.drop_zone.image_dropped.connect(self.handle_image_dropped)
            self.signals.append(signal)
            grid_layout.addWidget(signal, i // 2, i % 2)

        # Create control button
        self.control_button = QPushButton("Stop System")
        self.control_button.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: white;
                border: none;
                padding: 10px;
                font-size: 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff0000;
            }
        """)
        self.control_button.clicked.connect(self.toggle_system)
        
        main_layout.addLayout(grid_layout)
        main_layout.addWidget(self.control_button)
        central_widget.setLayout(main_layout)

    def setup_timer(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_system)
        self.timer.start(1000)  # Update every second

    def start_system(self):
        self.is_running = True
        self.control_button.setText("Stop System")
        self.control_button.setStyleSheet("""
            QPushButton {
                background-color: #cc0000;
                color: white;
                border: none;
                padding: 10px;
                font-size: 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #ff0000;
            }
        """)
        
        # Initialize first signal
        self.current_signal = 0
        self.next_signal = 1
        self.current_time = BASE_GREEN_TIME
        
        # Update UI
        self.signals[0].drop_zone.updateStyle("active")
        self.signals[0].update_timer(self.current_time, "green")
        
        self.signals[1].drop_zone.setAcceptDrops(True)
        self.signals[1].drop_zone.updateStyle("upload")
        self.signals[1].update_timer(self.current_time - BUFFER_TIME, "red")
        
        for i in range(2, 4):
            self.signals[i].drop_zone.updateStyle("inactive")
            self.signals[i].update_timer(0, "inactive")
        
        # Update Raspberry Pi
        self.update_raspberry_pi()

    def stop_system(self):
        self.is_running = False
        self.control_button.setText("Start System")
        self.control_button.setStyleSheet("""
            QPushButton {
                background-color: #00cc00;
                color: white;
                border: none;
                padding: 10px;
                font-size: 16px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #00ff00;
            }
        """)
        
        # Reset all signals
        for signal in self.signals:
            signal.drop_zone.setAcceptDrops(False)
            signal.drop_zone.updateStyle("inactive")
            signal.update_timer(0, "inactive")
        
        # Send stop command to Raspberry Pi
        try:
            requests.get(f"{API_BASE_URL}/stop")
        except RequestException as e:
            print(f"Error communicating with Raspberry Pi: {e}")

    def toggle_system(self):
        if self.is_running:
            self.stop_system()
        else:
            self.start_system()

    def update_system(self):
        if not self.is_running:
            return
        
        self.current_time -= 1
        
        if self.current_time <= 0:
            self.switch_signals()
        elif self.current_time <= BUFFER_TIME:
            # Buffer period - yellow light for next signal
            self.signals[self.next_signal].drop_zone.updateStyle("buffer")
            self.signals[self.next_signal].update_timer(self.current_time, "yellow")
        
        # Update current signal
        if self.current_time > BUFFER_TIME:
            self.signals[self.current_signal].update_timer(self.current_time, "green")
        
        # Update next signal
        upload_time = self.current_time - BUFFER_TIME
        if upload_time > 0 and self.current_time > BUFFER_TIME:
            self.signals[self.next_signal].update_timer(upload_time, "red")
        
        # Update Raspberry Pi
        self.update_raspberry_pi()

    def switch_signals(self):
        # Reset current signal
        self.signals[self.current_signal].drop_zone.setAcceptDrops(False)
        self.signals[self.current_signal].drop_zone.updateStyle("inactive")
        self.signals[self.current_signal].update_timer(0, "inactive")
        
        # Move to next signal
        self.current_signal = (self.current_signal + 1) % 4
        self.next_signal = (self.current_signal + 1) % 4
        
        # Reset timer
        if self.new_green_time is not None:
            self.current_time = self.new_green_time
            self.new_green_time = None
        else:
            self.current_time = BASE_GREEN_TIME
        
        # Update new current signal
        self.signals[self.current_signal].drop_zone.updateStyle("active")
        self.signals[self.current_signal].update_timer(self.current_time, "green")
        
        # Update new next signal
        self.signals[self.next_signal].drop_zone.setAcceptDrops(True)
        self.signals[self.next_signal].drop_zone.updateStyle("upload")
        self.signals[self.next_signal].update_timer(self.current_time - BUFFER_TIME, "red")

    def update_raspberry_pi(self):
        try:
            data = {
                "current_signal": self.current_signal,
                "next_signal": self.next_signal,
                "current_time": self.current_time,
                "is_buffer": self.current_time <= BUFFER_TIME
            }
            requests.post(f"{API_BASE_URL}/update", json=data)
        except RequestException as e:
            print(f"Error communicating with Raspberry Pi: {e}")

    def handle_image_dropped(self, file_path, signal_id):
        if signal_id != self.next_signal:
            return
        
        def process_image():
            try:
                with open(file_path, "rb") as image_file:
                    files = {'image': image_file}
                    response = requests.post(
                        f"{API_BASE_URL}/process_image?signal={signal_id}",
                        files=files
                    )
                    if response.status_code == 200:
                        data = response.json()
                        vehicle_count = data['vehicle_count']
                        # Calculate green time based on vehicle count and desired traffic flow rate
                        green_time = BASE_GREEN_TIME + (vehicle_count // VEHICLES_PER_SECOND)
                        self.new_green_time = min(MAX_GREEN_TIME, green_time)
                        print(f"Vehicle count: {vehicle_count}, Green time: {self.new_green_time}")
                    else:
                        print(f"Error processing image: {response.text}")
            except Exception as e:
                print(f"Error uploading image: {e}")

        # Run image processing in a separate thread to avoid UI lag
        threading.Thread(target=process_image).start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
