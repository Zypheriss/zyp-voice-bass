import sys
import os
import numpy as np
import sounddevice as sd
import wave
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSlider, QPushButton, QFileDialog, QComboBox, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from scipy.signal import butter, lfilter
from pydub import AudioSegment
from pydub.playback import play
import soundfile as sf
import time

class AudioProcessor:
    def __init__(self):
        self.mic_volume = 1.0
        self.headphone_volume = 1.0
        self.bass_level = 0.0
        self.treble_level = 0.0
        self.noise_reduction = True
        self.sample_rate = 44100
        self.max_safe_volume = 200
        self.stream = None
        self.soundpad_sounds = {}
        self.recording = False
        self.recorded_audio = []

    def apply_bass(self, data):
        if self.bass_level == 0:
            return data
        b, a = butter(2, 150 / self.sample_rate, btype='low')
        bass = lfilter(b, a, data)
        return data + self.bass_level * bass

    def apply_treble(self, data):
        if self.treble_level == 0:
            return data
        b, a = butter(2, 5000 / self.sample_rate, btype='high')
        treble = lfilter(b, a, data)
        return data + self.treble_level * treble

    def apply_noise_reduction(self, data):
        if self.noise_reduction:
            return nr.reduce_noise(y=data, sr=self.sample_rate)
        return data

    def load_sound(self, file_path):
        if os.path.exists(file_path):
            sound = AudioSegment.from_file(file_path)
            self.soundpad_sounds[file_path] = sound
            print(f"Soundpad: {file_path} yüklendi.")
        else:
            print(f"Soundpad: {file_path} bulunamadı!")

    def play_sound(self, file_path):
        if file_path in self.soundpad_sounds:
            sound = self.soundpad_sounds[file_path]
            play(sound)
        else:
            print("Soundpad: Ses bulunamadı!")

    def process_audio(self, indata, outdata, frames, time, status):
        if status:
            print(f"Status: {status}")
        if len(self.soundpad_sounds) > 0:
            audio = np.zeros_like(indata[:, 0]) 
            audio = self.apply_bass(audio)  
            audio = self.apply_treble(audio)
            audio = self.apply_noise_reduction(audio)
            audio *= self.headphone_volume
            stereo = np.column_stack([audio, audio])  
            outdata[:] = stereo
        else:
            audio = indata[:, 0] * self.mic_volume
            audio = self.apply_bass(audio)
            audio = self.apply_treble(audio)
            audio = self.apply_noise_reduction(audio)
            audio *= self.headphone_volume
            stereo = np.column_stack([audio, audio]) 
            outdata[:] = stereo

    def start(self):
        if self.stream is None:
            self.stream = sd.Stream(channels=2, callback=self.process_audio, samplerate=self.sample_rate)
            self.stream.start()

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def start_recording(self):
        self.recording = True
        self.recorded_audio = []
        self.recording_thread = threading.Thread(target=self.record_audio)
        self.recording_thread.start()

    def stop_recording(self):
        self.recording = False
        self.recording_thread.join()
        self.save_recording()

    def record_audio(self):
        while self.recording:
            audio_data = sd.rec(int(self.sample_rate * 1), samplerate=self.sample_rate, channels=1)
            sd.wait()
            self.recorded_audio.append(audio_data)

    def save_recording(self):
        recorded_data = np.concatenate(self.recorded_audio, axis=0)
        recorded_data = np.int16(recorded_data * 32767)
        filename = QFileDialog.getSaveFileName(None, "Kaydet", "recording.wav", "WAV Files (*.wav)")[0]
        if filename:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(recorded_data.tobytes())


class VoiceBoosterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.processor = AudioProcessor()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("🎧 Voice Booster - Zypheris Bey")
        self.setFixedSize(700, 700)
        self.setStyleSheet("""
            QWidget {
                background-color: #222;
                color: white;
                font-family: 'Segoe UI';
            }
            QLabel {
                font-size: 16px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 10px;
                background: #333;
                margin: 2px 0;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #00d9ff;
                border: 1px solid #5c5c5c;
                width: 18px;
                height: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QPushButton {
                background-color: #00d9ff;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #009bff;
            }
        """)

        username = os.getlogin().capitalize()
        welcome = QLabel(f"👋 Hoşgeldiniz, {username} Bey", self)
        welcome.setAlignment(Qt.AlignCenter)
        welcome.setFont(QFont("Arial", 18, QFont.Bold))

        mic_label = QLabel("🎙 Mikrofon Gücü", self)
        mic_slider = QSlider(Qt.Horizontal)
        mic_slider.setRange(1, self.processor.max_safe_volume)
        mic_slider.setValue(100)
        mic_slider.valueChanged.connect(lambda v: self.set_mic_volume(v))

        hp_label = QLabel("🎧 Kulaklık Gücü", self)
        hp_slider = QSlider(Qt.Horizontal)
        hp_slider.setRange(1, self.processor.max_safe_volume)
        hp_slider.setValue(100)
        hp_slider.valueChanged.connect(lambda v: self.set_headphone_volume(v))

        bass_label = QLabel("🎵 Bass Seviyesi", self)
        bass_slider = QSlider(Qt.Horizontal)
        bass_slider.setRange(0, 100)
        bass_slider.setValue(0)
        bass_slider.valueChanged.connect(lambda v: setattr(self.processor, 'bass_level', v / 100))

        treble_label = QLabel("🎶 Tiz Seviyesi", self)
        treble_slider = QSlider(Qt.Horizontal)
        treble_slider.setRange(0, 100)
        treble_slider.setValue(0)
        treble_slider.valueChanged.connect(lambda v: setattr(self.processor, 'treble_level', v / 100))

        start_button = QPushButton("Başlat", self)
        start_button.clicked.connect(self.toggle_start_stop)

        record_button = QPushButton("Kayıt Başlat", self)
        record_button.clicked.connect(self.toggle_recording)

        load_sound_button = QPushButton("Soundpad Yükle", self)
        load_sound_button.clicked.connect(self.load_sound)

        layout = QVBoxLayout()
        layout.addWidget(welcome)
        layout.addWidget(mic_label)
        layout.addWidget(mic_slider)
        layout.addWidget(hp_label)
        layout.addWidget(hp_slider)
        layout.addWidget(bass_label)
        layout.addWidget(bass_slider)
        layout.addWidget(treble_label)
        layout.addWidget(treble_slider)
        layout.addWidget(start_button)
        layout.addWidget(record_button)
        layout.addWidget(load_sound_button)

        self.setLayout(layout)

    def set_mic_volume(self, value):
        self.processor.mic_volume = value / 100

    def set_headphone_volume(self, value):
        self.processor.headphone_volume = value / 100

    def toggle_start_stop(self):
        if self.processor.stream is None:
            self.processor.start()
        else:
            self.processor.stop()

    def toggle_recording(self):
        if self.processor.recording:
            self.processor.stop_recording()
        else:
            self.processor.start_recording()

    def load_sound(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Ses Dosyası Yükle", "", "Audio Files (*.wav *.mp3 *.ogg)")
        if file_path:
            self.processor.load_sound(file_path)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VoiceBoosterApp()
    window.show()
    sys.exit(app.exec_())
