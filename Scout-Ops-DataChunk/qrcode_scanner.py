import io
import sys
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import os
import datetime
import time
import csv
import re
import threading
import platform
import gc
import psutil
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QPushButton, 
                            QWidget, QFileDialog, QHBoxLayout, QGridLayout, QGroupBox,
                            QComboBox, QCheckBox, QSlider, QFrame, QSplitter)
from PyQt5.QtGui import QImage, QPixmap, QColor, QPainter, QPen, QFont
from PyQt5.QtCore import QTimer, Qt, QRect, pyqtSignal, QThread, QUrl, QBuffer, QIODevice
from PyQt5.QtMultimedia import QSoundEffect
from PIL import Image, ImageEnhance, ImageOps
import subprocess  # For opening the folder
import warnings  # To suppress warnings

# Suppress zbar warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

# Replace the get_application_path function with these functions
def get_application_path():
    """Get the base application path regardless of how the app is launched"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def get_data_directory():
    """Get a writable directory for data storage"""
    if platform.system() == "Windows":
        # Use AppData folder on Windows
        base_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "ScoutOps")
    else:
        # Use home directory for other platforms
        base_dir = os.path.join(os.path.expanduser("~"), ".scoutops")
    
    # Create the directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

# Update your directory paths to use the data directory
SAVE_DIR = os.path.join(get_data_directory(), "scanned_data")
os.makedirs(SAVE_DIR, exist_ok=True)

# Update results path too
RESULTS_CSV = os.path.join(get_data_directory(), "results.csv")

# CSV header for reference
CSV_HEADER = "teamNumber,scouterName,matchKey,allianceColor,eventKey,station,matchNumber,auton_CoralScoringLevel1,auton_CoralScoringLevel2,auton_CoralScoringLevel3,auton_CoralScoringLevel4,auton_LeftBarge,auton_AlgaeScoringProcessor,auton_AlgaeScoringBarge,botLocation,teleop_CoralScoringLevel1,teleop_CoralScoringLevel2,teleop_CoralScoringLevel3,teleop_CoralScoringLevel4,teleop_AlgaeScoringBarge,teleop_AlgaeScoringProcessor,teleop_AlgaePickUp,teleop_Defense,endgame_Deep_Climb,endgame_Shallow_Climb,endgame_Park,endgame_Comments"

# Track which tablets have been scanned for current match
scanned_tablets = {
    "Red 1": False,
    "Red 2": False,
    "Red 3": False,
    "Blue 1": False,
    "Blue 2": False,
    "Blue 3": False
}

# Colors for UI
UI_COLORS = {
    "background": QColor(245, 245, 245),    # Light background
    "panel": QColor(255, 255, 255),         # White panel
    "panel_border": QColor(220, 220, 220),  # Light gray border
    "accent": QColor(0, 120, 212),          # Blue accent
    "accent_secondary": QColor(83, 152, 255), # Lighter blue
    "text": QColor(50, 50, 50),             # Dark text
    "text_secondary": QColor(120, 120, 120),# Secondary text
    "success": QColor(46, 160, 67),         # Green success
    "warning": QColor(250, 173, 20),        # Orange warning
    "error": QColor(220, 53, 69),           # Red error
    "red_alliance": QColor(220, 53, 69),    # Red alliance
    "blue_alliance": QColor(13, 110, 253),  # Blue alliance
    "divider": QColor(230, 230, 230),       # Light divider
}

# QR detection settings
qr_detection_settings = {
    "brightness_threshold": 160,  # Threshold for bright area detection (0-255)
    "min_rect_size": 50,          # Minimum rectangle size in pixels
    "max_rect_size": 500,         # Maximum rectangle size in pixels
    "rect_aspect_ratio": 1.5,     # Maximum aspect ratio for rectangles
    "focus_enabled": True,        # Enable/disable smart focusing
    "highlight_potential": True,  # Highlight potential QR code areas
}

class CameraThread(QThread):
    frame_ready = pyqtSignal(bytes)

    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.running = False
        self.capture = None

    def run(self):
        import cv2  # Import locally to avoid unnecessary overhead when not running
        self.capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Lower resolution for faster processing
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.capture.set(cv2.CAP_PROP_FPS, 30)  # Higher FPS for smoother video
        self.running = True

        while self.running:
            ret, frame = self.capture.read()
            if ret:
                # Convert frame to bytes for lightweight processing
                _, buffer = cv2.imencode('.jpg', frame)
                self.frame_ready.emit(buffer.tobytes())
            else:
                print(f"Error reading from camera {self.camera_index}")
                break

        self.capture.release()

    def stop(self):
        self.running = False
        self.wait()
        if self.capture:
            self.capture.release()
            self.capture = None

class QRCodeScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scout Ops QR Scanner")
        self.setGeometry(100, 100, 1280, 720)

        # Apply a lightweight stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QLabel { font-family: 'Segoe UI', sans-serif; font-size: 14px; }
            QPushButton { background-color: #0078d4; color: white; border-radius: 5px; padding: 10px 20px; }
            QPushButton:hover { background-color: #005a9e; }
            QGroupBox { font-family: 'Segoe UI', sans-serif; font-size: 16px; font-weight: bold; border: 1px solid #dcdcdc; border-radius: 8px; margin-top: 10px; padding: 10px; }
            QFrame { background-color: white; border-radius: 8px; padding: 10px; }
            QVBoxLayout, QHBoxLayout { spacing: 15px; margin: 15px; }
        """)

        # Memory management
        self.memory_monitor_timer = QTimer()
        self.memory_monitor_timer.timeout.connect(self.check_memory_usage)
        self.memory_monitor_timer.start(30000)  # Check every 30 seconds
        
        self.last_gc_time = time.time()
        
        # Limit size of history
        self.max_history_size = 100
        
        # State variables
        self.available_cameras = self.scan_available_cameras()
        self.active_camera_index = 0
        self.last_match_key = None
        self.last_scan_time = 0
        self.recent_messages = []
        self.scanned_data_history = set()
        
        # Central widget and main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        
        # Left panel (control panel)
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        
        # Add spacious margins to the left panel
        self.left_layout.setContentsMargins(20, 20, 20, 20)
        self.left_layout.setSpacing(20)

        # Tablet status group
        self.tablet_status_group = QGroupBox("Tablet Status")
        self.tablet_status_layout = QGridLayout()
        self.tablet_status_group.setLayout(self.tablet_status_layout)
        
        # Create tablet status labels
        self.tablet_labels = {}
        row = 0
        
        # Red Alliance label
        red_alliance_label = QLabel("RED ALLIANCE")
        red_alliance_label.setStyleSheet(f"color: {self.to_stylesheet_color(UI_COLORS['red_alliance'])}; font-weight: bold;")
        self.tablet_status_layout.addWidget(red_alliance_label, row, 0, 1, 2)
        row += 1
        
        # Red tablets
        for i in range(3):
            tablet_key = f"Red {i+1}"
            status_frame = QFrame()
            status_frame.setFrameShape(QFrame.StyledPanel)
            status_frame.setStyleSheet("background-color: white; border-radius: 5px; padding: 5px;")
            
            status_layout = QHBoxLayout(status_frame)
            tablet_label = QLabel(f"Tablet {i+1}:")
            status_label = QLabel("WAITING...")
            status_label.setStyleSheet("color: gray;")
            
            status_layout.addWidget(tablet_label)
            status_layout.addWidget(status_label)
            
            self.tablet_status_layout.addWidget(status_frame, row, 0, 1, 2)
            self.tablet_labels[tablet_key] = status_label
            row += 1
        
        # Blue Alliance label
        blue_alliance_label = QLabel("BLUE ALLIANCE")
        blue_alliance_label.setStyleSheet(f"color: {self.to_stylesheet_color(UI_COLORS['blue_alliance'])}; font-weight: bold;")
        self.tablet_status_layout.addWidget(blue_alliance_label, row, 0, 1, 2)
        row += 1
        
        # Blue tablets
        for i in range(3):
            tablet_key = f"Blue {i+1}"
            status_frame = QFrame()
            status_frame.setFrameShape(QFrame.StyledPanel)
            status_frame.setStyleSheet("background-color: white; border-radius: 5px; padding: 5px;")
            
            status_layout = QHBoxLayout(status_frame)
            tablet_label = QLabel(f"Tablet {i+1}:")
            status_label = QLabel("WAITING...")
            status_label.setStyleSheet("color: gray;")
            
            status_layout.addWidget(tablet_label)
            status_layout.addWidget(status_label)
            
            self.tablet_status_layout.addWidget(status_frame, row, 0, 1, 2)
            self.tablet_labels[tablet_key] = status_label
            row += 1
        
        self.left_layout.addWidget(self.tablet_status_group)
        
        # Detection settings group
        self.settings_group = QGroupBox("Detection Settings")
        self.settings_layout = QVBoxLayout()
        self.settings_group.setLayout(self.settings_layout)
        
        # Focus mode checkbox
        self.focus_checkbox = QCheckBox("Smart Focus")
        self.focus_checkbox.setChecked(qr_detection_settings["focus_enabled"])
        self.focus_checkbox.toggled.connect(self.toggle_focus_mode)
        self.settings_layout.addWidget(self.focus_checkbox)
        
        # Highlight potential regions checkbox
        self.highlight_checkbox = QCheckBox("Highlight Potential Regions")
        self.highlight_checkbox.setChecked(qr_detection_settings["highlight_potential"])
        self.highlight_checkbox.toggled.connect(self.toggle_highlight_mode)
        self.settings_layout.addWidget(self.highlight_checkbox)
        
        # Brightness threshold slider
        brightness_layout = QHBoxLayout()
        brightness_layout.addWidget(QLabel("Brightness:"))
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setMinimum(50)
        self.brightness_slider.setMaximum(255)
        self.brightness_slider.setValue(qr_detection_settings["brightness_threshold"])
        self.brightness_slider.valueChanged.connect(self.update_brightness)
        brightness_layout.addWidget(self.brightness_slider)
        self.brightness_value = QLabel(str(qr_detection_settings["brightness_threshold"]))
        brightness_layout.addWidget(self.brightness_value)
        self.settings_layout.addLayout(brightness_layout)
        
        self.left_layout.addWidget(self.settings_group)

        # Add left panel to main layout
        self.main_layout.addWidget(self.left_panel, 1)

        # Center panel (video)
        self.center_panel = QWidget()
        self.center_layout = QVBoxLayout(self.center_panel)
        
        # Title and instructions
        title_layout = QHBoxLayout()
        self.title_label = QLabel("SCOUT OPS - QR SCANNER")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(self.title_label)
        self.center_layout.addLayout(title_layout)
        
        instructions_label = QLabel("Point camera at QR codes to scan")
        instructions_label.setStyleSheet(f"color: {self.to_stylesheet_color(UI_COLORS['text_secondary'])};")
        instructions_label.setAlignment(Qt.AlignCenter)
        self.center_layout.addWidget(instructions_label)
        
        # Video display label
        self.video_label = QLabel("Camera feed will appear here")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            background-color: #e0e0e0;
            border: 1px solid #dcdcdc;
            border-radius: 8px;
        """)
        self.center_layout.addWidget(self.video_label)
        
        # Key shortcuts info
        shortcuts_frame = QFrame()
        shortcuts_frame.setFrameShape(QFrame.StyledPanel)
        shortcuts_layout = QHBoxLayout(shortcuts_frame)
        shortcuts_label = QLabel("Press 'q' to quit | 'f' for fullscreen | 'n'/'p' to switch cameras")
        shortcuts_label.setStyleSheet(f"color: {self.to_stylesheet_color(UI_COLORS['text_secondary'])};")
        shortcuts_layout.addWidget(shortcuts_label)
        self.center_layout.addWidget(shortcuts_frame)
        
        # Add center panel to main layout
        self.main_layout.addWidget(self.center_panel, 3)
        
        # Right panel
        self.right_panel = QWidget()
        self.right_layout = QVBoxLayout(self.right_panel)
        
        # Add spacious margins to the right panel
        self.right_layout.setContentsMargins(20, 20, 20, 20)
        self.right_layout.setSpacing(20)

        # Match info group
        self.match_info_group = QGroupBox("Match Info")
        self.match_info_layout = QVBoxLayout()
        self.match_info_group.setLayout(self.match_info_layout)
        
        self.match_key_label = QLabel("No Active Match")
        self.match_key_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.match_info_layout.addWidget(self.match_key_label)
        
        self.match_status_label = QLabel("Scan QR code to begin")
        self.match_info_layout.addWidget(self.match_status_label)
        
        # Progress bar frame
        self.progress_frame = QFrame()
        self.progress_frame.setMinimumHeight(25)
        self.progress_frame.setStyleSheet("background-color: #f0f0f0; border-radius: 5px;")
        self.match_info_layout.addWidget(self.progress_frame)
        
        self.progress_label = QLabel("0% Complete")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet("""
            font-family: 'Segoe UI', sans-serif;
            font-size: 14px;
            color: #0078d4;
        """)
        self.match_info_layout.addWidget(self.progress_label)
        
        self.tablets_count_label = QLabel("0/6 Tablets Scanned")
        self.match_info_layout.addWidget(self.tablets_count_label)
        
        self.right_layout.addWidget(self.match_info_group)
        
        # Activity log group
        self.log_group = QGroupBox("Activity Log")
        self.log_layout = QVBoxLayout()
        self.log_group.setLayout(self.log_layout)
        
        self.log_labels = []
        for i in range(5):
            log_label = QLabel("No recent activity")
            log_label.setStyleSheet(f"color: {self.to_stylesheet_color(UI_COLORS['text_secondary'])};")
            self.log_layout.addWidget(log_label)
            self.log_labels.append(log_label)
        
        self.right_layout.addWidget(self.log_group)
        
        # Camera controls group
        self.camera_group = QGroupBox("Camera Controls")
        self.camera_layout = QVBoxLayout()
        self.camera_group.setLayout(self.camera_layout)

        # Camera selector
        camera_select_layout = QHBoxLayout()
        camera_select_layout.addWidget(QLabel("Camera:"))
        self.camera_combo = QComboBox()
        for camera in self.available_cameras:
            self.camera_combo.addItem(camera["name"], camera["index"])
        self.camera_combo.currentIndexChanged.connect(self.switch_camera)
        camera_select_layout.addWidget(self.camera_combo)
        self.camera_layout.addLayout(camera_select_layout)

        # Camera buttons
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("Start Camera")
        self.start_button.clicked.connect(self.start_camera)
        button_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Camera")
        self.stop_button.clicked.connect(self.stop_camera)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        self.camera_layout.addLayout(button_layout)

        # Fullscreen button
        self.fullscreen_button = QPushButton("Toggle Fullscreen")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.camera_layout.addWidget(self.fullscreen_button)

        # Save data button
        self.save_button = QPushButton("Save QR Data")
        self.save_button.clicked.connect(self.manual_save_qr_data)
        self.save_button.setEnabled(False)
        self.camera_layout.addWidget(self.save_button)

        # Add "Check CSV Data" button to the right panel
        self.check_csv_button = QPushButton("Check CSV Data")
        self.check_csv_button.clicked.connect(self.check_csv_data)
        self.right_layout.addWidget(self.check_csv_button)

        # Add "Open Save Folder" button to the right panel
        self.open_folder_button = QPushButton("Open Save Folder")
        self.open_folder_button.clicked.connect(self.open_save_folder)
        self.right_layout.addWidget(self.open_folder_button)

        self.right_layout.addWidget(self.camera_group)

        # Add right panel to main layout
        self.main_layout.addWidget(self.right_panel, 1)
        
        # Camera thread and timer setup
        self.camera_thread = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)  # Update UI every 100ms
        
        # QR code data
        self.qr_data = None
        self.is_fullscreen = False
        
        # Keyboard shortcuts
        self.installEventFilter(self)
        
        # Start with the first camera
        if self.available_cameras:
            self.start_camera()
    
    def eventFilter(self, obj, event):
        if event.type() == event.KeyPress:
            key = event.key()
            if key == Qt.Key_Q:
                self.close()
                return True
            elif key == Qt.Key_F:
                self.toggle_fullscreen()
                return True
            elif key == Qt.Key_N:
                self.next_camera()
                return True
            elif key == Qt.Key_P:
                self.prev_camera()
                return True
        return super().eventFilter(obj, event)
    
    def to_stylesheet_color(self, qcolor):
        return f"rgb({qcolor.red()}, {qcolor.green()}, {qcolor.blue()})"
    
    def scan_available_cameras(self):
        """Scan system for available cameras"""
        available_cameras = []
        system = platform.system()
        
        # Different approach based on OS
        if system == "Windows":
            # Try the first 5 camera indices
            for i in range(5):
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        cap.release()
                        camera_name = f"Camera {i+1}"
                        available_cameras.append({"index": i, "name": camera_name})
                    else:
                        cap.release()
        else:
            # Linux/Mac approach
            for i in range(5):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        cap.release()
                        camera_name = f"Camera {i+1}"
                        available_cameras.append({"index": i, "name": camera_name})
                    else:
                        cap.release()
        
        if not available_cameras:
            print("No cameras found")
            available_cameras.append({"index": 0, "name": "Default Camera"})
        
        print(f"Found {len(available_cameras)} cameras: {[cam['name'] for cam in available_cameras]}")
        return available_cameras
    
    def start_camera(self):
        """Start the camera thread"""
        if self.camera_thread is not None and self.camera_thread.isRunning():
            self.stop_camera()
        
        camera_index = self.camera_combo.currentData()
        self.camera_thread = CameraThread(camera_index)
        self.camera_thread.frame_ready.connect(self.process_frame)
        self.camera_thread.start()
        
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.add_status_message(f"Started camera {camera_index}", "info")
    
    def stop_camera(self):
        """Stop the camera thread"""
        if self.camera_thread is not None and self.camera_thread.isRunning():
            self.camera_thread.stop()
            self.camera_thread = None
            self.video_label.setText("Camera feed stopped")
            
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.save_button.setEnabled(False)
            self.add_status_message("Camera stopped", "info")
    
    def switch_camera(self, _):
        """Switch to the selected camera"""
        if self.camera_thread is not None and self.camera_thread.isRunning():
            self.stop_camera()
            self.start_camera()
    
    def next_camera(self):
        """Switch to the next camera"""
        if self.camera_combo.count() > 1:
            next_index = (self.camera_combo.currentIndex() + 1) % self.camera_combo.count()
            self.camera_combo.setCurrentIndex(next_index)
    
    def prev_camera(self):
        """Switch to the previous camera"""
        if self.camera_combo.count() > 1:
            prev_index = (self.camera_combo.currentIndex() - 1) % self.camera_combo.count()
            self.camera_combo.setCurrentIndex(prev_index)
    
    def toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
            self.add_status_message("Exited fullscreen mode", "info")
        else:
            self.showFullScreen()
            self.add_status_message("Entered fullscreen mode", "info")
    
    def toggle_focus_mode(self, enabled):
        """Toggle smart focusing mode"""
        qr_detection_settings["focus_enabled"] = enabled
        mode = "enabled" if enabled else "disabled"
        self.add_status_message(f"Smart focusing {mode}", "info")
    
    def toggle_highlight_mode(self, enabled):
        """Toggle highlighting potential QR regions"""
        qr_detection_settings["highlight_potential"] = enabled
        mode = "enabled" if enabled else "disabled"
        self.add_status_message(f"Region highlighting {mode}", "info")
    
    def update_brightness(self, value):
        """Update brightness threshold"""
        qr_detection_settings["brightness_threshold"] = value
        self.brightness_value.setText(str(value))
    
    def update_ui(self):
        """Update UI elements that need periodic updates"""
        # Update tablet status
        self.update_tablet_status()
        
        # Update match info
        self.update_match_info()
    
    def update_tablet_status(self):
        """Update tablet status display"""
        for tablet_key, status in scanned_tablets.items():
            if tablet_key in self.tablet_labels:
                label = self.tablet_labels[tablet_key]
                if status:
                    label.setText("✓ SCANNED")
                    label.setStyleSheet(f"color: {self.to_stylesheet_color(UI_COLORS['success'])}; font-weight: bold;")
                else:
                    label.setText("WAITING...")
                    label.setStyleSheet("color: gray;")
    
    def update_match_info(self):
        """Update match information display"""
        if self.last_match_key:
            self.match_key_label.setText(self.last_match_key)
            
            # Calculate completeness
            scanned_count = sum(1 for status in scanned_tablets.values() if status)
            total_tablets = len(scanned_tablets)
            percent_complete = int((scanned_count / total_tablets) * 100)
            
            self.progress_label.setText(f"{percent_complete}% Complete")
            self.tablets_count_label.setText(f"{scanned_count}/{total_tablets} Tablets Scanned")
            
            # Update progress bar (drawn in paintEvent of progress_frame)
            self.progress_frame.setProperty("progress", percent_complete/100)
            self.progress_frame.setStyleSheet(
                f"background-color: #f0f0f0; border-radius: 5px; "
                f"background-color: {self.to_stylesheet_color(UI_COLORS['accent'])};"
            )
            self.progress_frame.update()
        else:
            self.match_key_label.setText("No Active Match")
            self.match_status_label.setText("Scan QR code to begin")
            self.progress_label.setText("0% Complete")
            self.tablets_count_label.setText("0/6 Tablets Scanned")
    
    def add_status_message(self, message, message_type="info"):
        """Add a message to the status message queue"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        color = UI_COLORS["text"]
        
        if message_type == "success":
            color = UI_COLORS["success"]
        elif message_type == "warning":
            color = UI_COLORS["warning"]
        elif message_type == "error":
            color = UI_COLORS["error"]
        
        self.recent_messages.append({
            "text": f"[{timestamp}] {message}",
            "color": color,
            "time_added": time.time()
        })
        
        # Keep only the last 5 messages
        if len(self.recent_messages) > 5:
            self.recent_messages.pop(0)
        
        # Update the log labels
        for i, (label, msg) in enumerate(zip(self.log_labels, reversed(self.recent_messages))):
            label.setText(msg["text"])
            label.setStyleSheet(f"color: {self.to_stylesheet_color(msg['color'])};")
        
        # Fill remaining labels with empty text
        for i in range(len(self.recent_messages), len(self.log_labels)):
            self.log_labels[i].setText("")
    
    def find_potential_qr_regions(self, frame):
        """Find bright rectangular regions that might contain QR codes."""
        # Remove all filtering logic to keep the camera feed unfiltered
        return []

    def process_frame(self, frame_bytes):
        """Process a frame from the camera."""
        try:
            # Convert bytes to PIL Image
            pil_image = Image.open(io.BytesIO(frame_bytes)).convert("RGB")

            # Decode QR codes using pyzbar directly on the PIL image
            detected_codes = decode(pil_image)

            # Prepare the image for display (convert to QImage)
            q_img = QImage(pil_image.tobytes(), pil_image.width, pil_image.height, QImage.Format_RGB888)

            # Process detected QR codes
            for code in detected_codes:
                qr_data = code.data.decode('utf-8')

                # Check for duplicates
                if qr_data in self.scanned_data_history:
                    # Play duplicate sound
                    if hasattr(self, 'duplicate_sound') and self.duplicate_sound is not None:
                        self.duplicate_sound.play()
                    self.add_status_message(f"QR code already scanned: {qr_data[:30]}...", "warning")
                    continue

                # Add to scanned history
                self.scanned_data_history.add(qr_data)

                # Identify the tablet and update status
                tablet_id = self.identify_tablet(qr_data)
                if tablet_id and tablet_id in scanned_tablets:
                    scanned_tablets[tablet_id] = True
                    self.update_tablet_status()

                # Save the QR data
                self.save_qr_data(qr_data, tablet_id)

                # Add status message
                self.add_status_message(f"Scanned data from {tablet_id or 'Unknown'}", "success")

                # Play success sound
                if hasattr(self, 'success_sound') and self.success_sound is not None:
                    self.success_sound.play()

                print(f"Scanned QR Code: {qr_data[:30]}...")

            # Update the video label with the unfiltered image
            self.video_label.setPixmap(QPixmap.fromImage(q_img))

        except Exception as e:
            print(f"Error processing frame: {e}")
            import traceback
            traceback.print_exc()

    def identify_tablet(self, csv_data):
        """Identify which tablet the data came from based on CSV values"""
        try:
            print("Heelo")
            parts = csv_data.split(',')
            if len(parts) < 6:
                return None
                
            alliance_color = parts[3]  # allianceColor (Red/Blue)
            station = parts[5]        # station (1,2,3)

            
            if alliance_color and station:
                return f"{alliance_color} {station}"
            return None
        except Exception as e:
            print(f"Error identifying tablet: {e}")
            return None
    
    def get_match_key(self, csv_data):
        """Extract match key from CSV data"""
        try:
            parts = csv_data.split(',')
            if len(parts) < 4:
                return None
            return parts[2]  # matchKey
        except:
            return None
    
    def sanitize_csv_data(self, data):
        """Sanitize CSV data to handle commas in string fields."""
        print("Sanitizing CSV data...")
        print(data)
        sanitized_data = []
        for field, value in zip(CSV_HEADER.split(','), data.split(',')):
            if field == "endgame_Comments":
                # Replace commas in the endgame_Comments field with a pipe (|) or another character
                value = value.replace(',', '|')
                print(value)
            sanitized_data.append(value)
            print(sanitized_data)
        return ','.join(sanitized_data)

    def save_qr_data(self, data, tablet_id=None):
        """Save the QR code data to a file and update tracking."""
        global scanned_tablets

        # Sanitize the data to handle commas in string fields
        data = self.sanitize_csv_data(data)

        # Remove quotes if present
        data = data.strip('"\'')
        
        # Extract match key to track matches
        match_key = self.get_match_key(data)
        
        # If we've moved to a new match, reset tablet tracking
        if match_key and match_key != self.last_match_key:
            self.last_match_key = match_key
            for key in scanned_tablets:
                scanned_tablets[key] = False
        
        # Mark this tablet as scanned
        if tablet_id:
            scanned_tablets[tablet_id] = True
        
        # Create unique filename with timestamp and tablet ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        tablet_suffix = f"_{tablet_id.replace(' ', '')}" if tablet_id else ""
        match_suffix = f"_{match_key}" if match_key else ""
        
        filename = f"qr_data{match_suffix}{tablet_suffix}_{timestamp}.csv"
        filepath = os.path.join(SAVE_DIR, filename)
        
        # Save data to individual file
        try:
            with open(filepath, 'w') as f:
                f.write(data)
            print(f"Data saved to {filepath}")
        except Exception as e:
            error_msg = f"Error saving file: {str(e)}"
            print(error_msg)
            self.add_status_message(error_msg, "error")
            return None
        
        # Also append to combined results CSV
        self.append_to_results_csv(data)
        
        return filepath
    
    def manual_save_qr_data(self):
        """Manually save the last QR code data"""
        if not self.qr_data:
            self.add_status_message("No QR code data to save", "warning")
            return
        
        tablet_id = self.identify_tablet(self.qr_data)
        filepath = self.save_qr_data(self.qr_data, tablet_id)
        self.add_status_message(f"Manually saved QR data to {os.path.basename(filepath)}", "success")
    
    def append_to_results_csv(self, data):
        """Append data to the combined results CSV file."""
        try:
            # Sanitize the data to handle commas in string fields
            data = self.sanitize_csv_data(data)

            # Check if file exists to determine if we need to write headers
            file_exists = os.path.isfile(RESULTS_CSV)

            # Convert the data string to a list of values
            data_values = data.split(',')

            # Open the file in append mode
            with open(RESULTS_CSV, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)

                # Write header if file is new
                if not file_exists:
                    header = CSV_HEADER.split(',')
                    writer.writerow(header)

                # Write the data row
                writer.writerow(data_values)

            print(f"Data appended to {RESULTS_CSV}")
        except Exception as e:
            error_msg = f"Error appending to results CSV: {str(e)}"
            print(error_msg)
            self.add_status_message(error_msg, "error")
    
    def create_match_summary_file(self):
        """Create a summary file for all tablets in a match"""
        if not self.last_match_key:
            return
        
        # Check if we have at least some data
        if not any(scanned_tablets.values()):
            return
        
        # Create a summary of which tablets were scanned
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"match_summary_{self.last_match_key}_{timestamp}.txt"
        filepath = os.path.join(SAVE_DIR, filename)
        
        with open(filepath, 'w') as f:
            f.write(f"Match Summary for {self.last_match_key}\n")
            f.write("=" * 40 + "\n")
            
            for tablet, scanned in scanned_tablets.items():
                status = "✓ SCANNED" if scanned else "✗ MISSING"
                f.write(f"{tablet}: {status}\n")
        
        print(f"Match summary saved to {filepath}")
        self.add_status_message(f"Match summary saved", "success")
    
    def validate_qr_data(self, data):
        """Validate the QR code data format"""
        try:
            # Split the data into parts
            parts = data.split(',')
            # Ensure the data has the correct number of fields
            if len(parts) != len(CSV_HEADER.split(',')):
                return False
            # Perform additional validation checks if necessary
            # Example: Check if teamNumber is numeric
            if not parts[0].isdigit():
                return False
            return True
        except Exception as e:
            print(f"Error validating QR data: {e}")
            return False
    
    def check_csv_data(self):
        """Check if the CSV file has all required headers and fix missing values."""
        try:
            if not os.path.exists(RESULTS_CSV):
                self.add_status_message("CSV file does not exist.", "error")
                return

            # Read the CSV file
            with open(RESULTS_CSV, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                rows = list(reader)

                # Check for missing headers
                missing_headers = [header for header in CSV_HEADER.split(',') if header not in reader.fieldnames]
                if missing_headers:
                    self.add_status_message(f"Missing headers: {', '.join(missing_headers)}. Fixing...", "warning")

                # Fix rows with missing headers
                fixed_rows = []
                for row in rows:
                    fixed_row = {header: row.get(header, "null") for header in CSV_HEADER.split(',')}
                    fixed_rows.append(fixed_row)

            # Write the fixed rows back to the CSV file
            with open(RESULTS_CSV, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADER.split(','))
                writer.writeheader()
                writer.writerows(fixed_rows)

            self.add_status_message("CSV data checked and fixed successfully.", "success")
        except Exception as e:
            self.add_status_message(f"Error checking CSV data: {e}", "error")
            print(f"Error checking CSV data: {e}")

    def check_memory_usage(self):
        """Monitor and manage memory usage"""
        current_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024  # MB
        memory_percent = psutil.virtual_memory().percent
        current_time = time.time()
        
        # Log memory usage periodically
        print(f"Memory usage: {current_memory:.1f} MB ({memory_percent}%)")
        
        # Perform cleanup if memory usage is high
        if memory_percent > 70 or current_time - self.last_gc_time > 600:  # 10 minutes
            self.cleanup_memory()
            self.last_gc_time = time.time()
    
    def cleanup_memory(self):
        """Perform memory cleanup tasks"""
        # Clear pixmap cache if it exists
        if hasattr(self, 'video_label') and isinstance(self.video_label, QLabel):
            self.video_label.setPixmap(QPixmap())
        
        # Limit size of scanned data history
        if len(self.scanned_data_history) > self.max_history_size:
            # Keep only the most recent entries
            self.scanned_data_history = set(list(self.scanned_data_history)[-self.max_history_size:])
        
        # Clear any cached data in widgets
        for widget in self.findChildren(QWidget):
            widget.setUpdatesEnabled(False)
            widget.setUpdatesEnabled(True)
        
        # Force garbage collection
        gc.collect()
        
        self.add_status_message("Memory cleanup performed", "info")
    
    def closeEvent(self, event):
        """Handle application close event"""
        self.stop_camera()
        self.create_match_summary_file()
        
        # Clear any large objects
        self.scanned_data_history.clear()
        
        # Final garbage collection
        gc.collect()
        event.accept()

    def setup_sounds(self):
        """Setup sound effects from WAV files in the working directory"""
        try:
            # Get app directory for sound files
            app_dir = get_application_path()

            # Success sound
            self.success_sound = QSoundEffect()
            success_path = os.path.join(app_dir, "woof.wav")
            if not os.path.exists(success_path):
                success_path = "woof.wav"  # Fallback to relative path
            self.success_sound.setSource(QUrl.fromLocalFile(os.path.abspath(success_path)))
            self.success_sound.setLoopCount(1)
            self.success_sound.setVolume(0.5)

            # Duplicate sound
            self.duplicate_sound = QSoundEffect()
            duplicate_path = os.path.join(app_dir, "qqq.wav")
            if not os.path.exists(duplicate_path):
                duplicate_path = "qqq.wav"  # Fallback to relative path
            self.duplicate_sound.setSource(QUrl.fromLocalFile(os.path.abspath(duplicate_path)))
            self.duplicate_sound.setLoopCount(1)
            self.duplicate_sound.setVolume(0.5)

            print("Sound files loaded successfully")
        except Exception as e:
            print(f"Error setting up sounds: {e}")
            self.success_sound = None
            self.duplicate_sound = None

    def open_save_folder(self):
        """Open the folder where all files are saved."""
        try:
            if platform.system() == "Windows":
                os.startfile(SAVE_DIR)
            elif platform.system() == "Darwin":  # macOS
                subprocess.Popen(["open", SAVE_DIR])
            else:  # Linux
                subprocess.Popen(["xdg-open", SAVE_DIR])
        except Exception as e:
            self.add_status_message(f"Error opening folder: {e}", "error")

# Custom QFrame for progress bar
class ProgressFrame(QFrame):
    def __init__(self, parent=None):
        super(ProgressFrame, self).__init__(parent)
        self.setProperty("progress", 0.0)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get progress value
        progress = self.property("progress")
        if progress is None:
            progress = 0.0
        
        # Get progress color
        progress_color = self.property("progressColor")
        if progress_color is None:
            progress_color = QColor(0, 120, 212)  # Default blue
        
        # Draw progress
        width = self.width() * progress
        painter.fillRect(0, 0, width, self.height(), progress_color)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QRCodeScannerApp()
    window.show()
    sys.exit(app.exec_())
