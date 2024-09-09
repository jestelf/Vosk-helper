import pandas as pd
import pyaudio
import webrtcvad
import json
import os
from vosk import Model, KaldiRecognizer
import threading
import queue
import ctypes
import webbrowser
import platform
import time
from PyQt5.QtWidgets import QTextEdit, QLabel, QDialog, QApplication, QVBoxLayout, QGroupBox, QHBoxLayout, \
    QPushButton, QComboBox
from PyQt5.QtGui import QIcon
from sys import argv, exit
import warnings
from keyboard import is_pressed
from playsound import playsound
from random import randint

warnings.simplefilter(action='ignore', category=FutureWarning)
pd.options.mode.chained_assignment = None


class MainWindow(QDialog):

    kernel32 = ctypes.WinDLL('kernel32')
    user32 = ctypes.WinDLL('user32')
    hWnd = kernel32.GetConsoleWindow()

    def __init__(self):
        super(MainWindow, self).__init__()

        self.data = pd.DataFrame()
        self.hello_phrases = ['audio\\doing.mp3', 'audio\\doing2.mp3', 'audio\\doing3.mp3']
        self.gb_phrases = ['audio\\gb.mp3', 'audio\\gb2.mp3']
        with open('data.csv', encoding='utf-8') as file:
            self.data = pd.read_csv(file)

        actions = ['открыть сайт', 'открыть приложение']

        self.play_icon = QIcon('icons\\play.png')
        self.stop_icon = QIcon('icons\\pause.png')
        save_icon = QIcon('icons\\save.png')
        self.settings_activation_record = False
        self.settings_command_record = False

        main_layout = QVBoxLayout()

        self.activation_word = list((self.data.loc[self.data['type'] == 'activation']['command']))[0]
        self.temp_activation_word = self.activation_word

        activation_group_box = QGroupBox('Activation Word')  # изменение активации
        activation_layout = QHBoxLayout()

        self.activation_word_label = QLabel(self.activation_word)  # текущее слово активации
        activation_layout.addWidget(self.activation_word_label)

        self.start_record_button = QPushButton()  # кнопка записи слова активации
        self.start_record_button.setIcon(self.play_icon)
        self.start_record_button.clicked.connect(self.activation_settings)
        activation_layout.addWidget(self.start_record_button)

        save_record_button = QPushButton()  # кнопка сохранения слова активации
        save_record_button.setIcon(save_icon)
        save_record_button.clicked.connect(self.save_activation_word)
        activation_layout.addWidget(save_record_button)

        main_layout.addWidget(activation_group_box)

        add_command_group_box = QGroupBox('Add Command')  # добавление команды
        add_command_layout = QHBoxLayout()

        self.choose_action = QComboBox()  # выбрать действие
        self.choose_action.addItems(actions)
        add_command_layout.addWidget(self.choose_action)

        self.command_word_label = QLabel('Add Command -> ')  # текущая команда
        add_command_layout.addWidget(self.command_word_label)

        self.start_command_button = QPushButton()  # кнопка записи команды
        self.start_command_button.setIcon(self.play_icon)
        self.start_command_button.clicked.connect(self.command_settings)
        add_command_layout.addWidget(self.start_command_button)

        save_command_button = QPushButton()  # кнопка сохранения команды
        save_command_button.setIcon(save_icon)
        save_command_button.clicked.connect(self.save_command)
        add_command_layout.addWidget(save_command_button)

        main_layout.addWidget(add_command_group_box)

        self.current_ref = QTextEdit('Enter your ref/way here')  # поле ввода ссылки
        main_layout.addWidget(self.current_ref)

        activation_group_box.setLayout(activation_layout)  # назначения лайаутов по виджетам
        add_command_group_box.setLayout(add_command_layout)

        self.setLayout(main_layout)

    @staticmethod
    def hide_console():
        MainWindow.user32.ShowWindow(MainWindow.hWnd, 0)

    @staticmethod
    def show_console():
        MainWindow.user32.ShowWindow(MainWindow.hWnd, 5)

    @staticmethod
    def audio_capture(stream, frame_size, vad, audio_queue):
        while True:
            frames = [stream.read(frame_size, exception_on_overflow=False) for _ in
                      range(5)]  # Уменьшаем количество фреймов
            audio_queue.put(b''.join(frames))

    @staticmethod
    def open_url(url):
        if platform.system() == "Windows":
            os.system(f"start {url}")
        elif platform.system() == "Darwin":
            os.system(f"open {url}")
        elif platform.system() == "Linux":
            os.system(f"xdg-open {url}")
        else:
            print("Неизвестная операционная система")

    def process_open_site_command(self, command):

        for i, row in self.data.iterrows():
            site_name = row.command
            site_url = row.url
            site_type = row.type
            if site_name in command and site_type == 'site':
                print(f"Попытка открыть сайт {site_name}")
                try:
                    self.open_url(site_url)
                    print(f"Сайт {site_name} открыт")

                    self.random_greets_answer()
                except Exception as e:
                    print(f"Ошибка при открытии сайта {site_name}: {e}")
                return True

        print("Название сайта не распознано")
        return False

    def process_open_app_command(self, command):

        for i, row in self.data.iterrows():
            app_name = row.command
            app_path = row.url
            app_type = row.type
            if app_name in command and app_type == 'app':
                print(f"Попытка открыть приложение {app_name}")
                try:
                    os.startfile(app_path)
                    print(f"Приложение {app_name} открыто")

                    self.random_greets_answer()
                except Exception as e:
                    print(f"Ошибка при открытии приложения {app_name}: {e}")
                return True

        print("Название приложения не распознано")
        return False

    def command_recognition(self, recognizer, audio_queue):
        console_hidden = False
        waiting_for_keyword = True
        partial_result = ''

        while True:
            data = audio_queue.get()
            if recognizer.AcceptWaveform(data):
                result_json = recognizer.Result()
                result = json.loads(result_json)
                command = result['text']

                if self.settings_activation_record:
                    self.temp_activation_word = command
                    self.activation_word_label.setText(command)

                if self.settings_command_record:
                    self.command_word_label.setText(command)

                if waiting_for_keyword and self.activation_word in command:
                    print("Ключевое слово распознано, ожидаю команду...")
                    playsound('audio\\listen.mp3')
                    waiting_for_keyword = False
                    if console_hidden:
                        self.show_console()
                        console_hidden = False
                    partial_result = ''
                    continue

                if waiting_for_keyword:
                    continue

                print(f"Распознанная команда: {command}")

                if "открой сайт" in command and self.process_open_site_command(command):
                    partial_result = ''

                elif "открой приложение" in command and self.process_open_app_command(command):
                    partial_result = ''

                elif "хайд" in command:
                    print("Выполняю команду 'Скройся'")
                    self.hide_console()
                    waiting_for_keyword = True
                    console_hidden = True
                    partial_result = ''

                elif "стоп" in command:
                    print(f"Ожидаю команду '{self.activation_word}' для активации")
                    waiting_for_keyword = True
                    self.random_gb_answer()
                    partial_result = ''

                elif "консоль" in command:
                    print("Открываю консоль...")
                    os.system("start cmd")

                elif "добавь сайт" in command:
                    request = command.replace('добавь сайт', '')
                    print(request)

                partial_result = ''

            else:
                partial_result += recognizer.PartialResult()

    def listen_for_commands(self, model_path, interface):
        vad = webrtcvad.Vad(1)

        model = Model(model_path)
        recognizer = KaldiRecognizer(model, 16000)

        mic = pyaudio.PyAudio()
        stream = mic.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=320)
        stream.start_stream()

        frame_duration_ms = 20
        frame_size = int(16000 * frame_duration_ms / 1000)

        audio_queue = queue.Queue()

        threading.Thread(target=self.audio_capture, args=(stream, frame_size, vad, audio_queue), daemon=True).start()
        threading.Thread(target=self.command_recognition, args=(recognizer, audio_queue), daemon=True).start()

        print("Слушаю...")

        while True:
            if is_pressed('ctrl') and is_pressed('shift') and is_pressed('h'):
                interface.exec_()

    def activation_settings(self):
        self.settings_activation_record = not self.settings_activation_record

        if self.settings_activation_record:
            self.start_record_button.setIcon(self.stop_icon)
        else:
            self.start_record_button.setIcon(self.play_icon)

    def save_activation_word(self):
        self.activation_word = self.temp_activation_word
        self.data.loc[0]['command'] = self.activation_word
        self.save_data()

    def command_settings(self):
        self.settings_command_record = not self.settings_command_record

        if self.settings_command_record:
            self.start_command_button.setIcon(self.stop_icon)
        else:
            self.start_command_button.setIcon(self.play_icon)

    def save_command(self):
        typo = ''
        if self.choose_action.currentText() == 'открыть сайт':
            typo = 'site'
        elif self.choose_action.currentText() == 'открыть приложение':
            typo = 'app'
        self.data.loc[len(self.data.index)] = [typo, self.command_word_label.text(),
                                               self.current_ref.toPlainText()]
        self.save_data()

    def random_greets_answer(self):
        phrase = randint(0, 2)
        playsound(self.hello_phrases[phrase])

    def random_gb_answer(self):
        phrase = randint(0, 1)
        playsound(self.gb_phrases[phrase])

    def save_data(self):
        self.data.to_csv('data.csv', encoding='utf-8', index=False)


if __name__ == "__main__":
    mod_path = f"{os.path.dirname(os.path.realpath(__file__))}\\vosk-model-small-ru-0.22"
    app = QApplication(argv)
    window = MainWindow()
    window.setWindowTitle('Helper')
    window.resize(10, 100)
    window.listen_for_commands(mod_path, window)
