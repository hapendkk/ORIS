import sys
import json
import socket
import threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QApplication, QPushButton, QHBoxLayout,
    QListWidget, QRadioButton, QListWidgetItem, QCheckBox, QLabel, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QObject

HOST = '127.0.0.1'
PORT = 65432

class TaskClient(QObject):
    tasks_updated = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.socket = None
        self.running = False

    def connect_to_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((HOST, PORT))
            self.running = True

            self.listen_thread = threading.Thread(target=self._listen_server)
            self.listen_thread.daemon = True
            self.listen_thread.start()
            print("Успешное подключение к серверу.")
            return True
        except ConnectionRefusedError:
            QMessageBox.critical(None, "Ошибка подключения",
                                 f"Не удалось подключиться к серверу по адресу {HOST}:{PORT}. Проверьте, запущен ли сервер.")
            return False
        except Exception as e:
            QMessageBox.critical(None, "Ошибка", f"Произошла ошибка при подключении: {e}")
            return False

    def _listen_server(self):
        data_buffer = ""
        while self.running:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break

                data_buffer += data.decode('utf-8')

                while '\n' in data_buffer:
                    message, data_buffer = data_buffer.split('\n', 1)

                    try:
                        command = json.loads(message)
                        if command.get("action") == "list_update":
                            self.tasks_updated.emit(command["tasks"])

                    except json.JSONDecodeError:
                        print("Ошибка декодирования JSON")

            except ConnectionResetError:
                print("Соединение с сервером сброшено.")
                break
            except Exception as e:
                if self.running:
                    print(f"Ошибка в цикле прослушивания: {e}")
                break

        self.disconnect_from_server()

    def send_command(self, command):
        if self.socket:
            try:
                message = json.dumps(command) + '\n'
                self.socket.sendall(message.encode('utf-8'))
            except Exception as e:
                print(f"Ошибка при отправке команды: {e}")
                self.disconnect_from_server()

    def disconnect_from_server(self):
        if self.socket:
            self.running = False
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            self.socket = None
            print("Соединение с сервером разорвано.")


#исходный скелетик с таском
class TaskWidget(QWidget):
    completion_changed = pyqtSignal(int, bool)

    def __init__(self, text, priority, completed, index):
        super().__init__()
        self.text = text
        self.priority = priority
        self.index = index
        self.completed = completed

        layout = QHBoxLayout(self)

        self.checkbox = QCheckBox()
        self.checkbox.stateChanged.connect(self.update_style_and_emit)

        self.label = QLabel(text)

        if completed:
            self.label.setStyleSheet("color: gray; text-decoration: line-through;")
        else:
            self.apply_priority_style()

        self.checkbox.setChecked(completed)

        layout.addWidget(self.checkbox)
        layout.addWidget(self.label)

    def apply_priority_style(self):
        colors = {
            "high": "red",
            "medium": "orange",
            "low": "green"
        }
        color = colors.get(self.priority)
        self.label.setStyleSheet(f"color: {color}; font-weight: bold")

    def update_style_and_emit(self, state):
        self.completed = state == 2

        if self.completed:
            self.label.setStyleSheet("color: gray; text-decoration: line-through;")
        else:
            self.apply_priority_style()

        self.completion_changed.emit(self.index, self.completed)

    def set_completed_from_server(self, completed):
        self.completed = completed

        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(completed)
        self.checkbox.blockSignals(False)

        if self.completed:
            self.label.setStyleSheet("color: gray; text-decoration: line-through;")
        else:
            self.apply_priority_style()

class TaskManager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Мульти - Task Manager")

        self.client = TaskClient()
        if not self.client.connect_to_server():
            QApplication.quit()
            return

        self.client.tasks_updated.connect(self.update_gui)
        self.current_tasks = []

        layout = QVBoxLayout(self)
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Введите задачу...")

        buttons_layout = QHBoxLayout()

        add_button = QPushButton("Добавить задачу")
        delete_button = QPushButton("Удалить выбранную задачу")
        clear_completed_task = QPushButton("Удалить все выполненные")

        self.tasks_list = QListWidget()

        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(delete_button)
        buttons_layout.addWidget(clear_completed_task)

        priority_layout = QHBoxLayout()

        self.low_priority = QRadioButton("Низкий")
        self.medium_priority = QRadioButton("Средний")
        self.high_priority = QRadioButton("Высокий")

        self.medium_priority.setChecked(True)

        priority_layout.addWidget(self.low_priority)
        priority_layout.addWidget(self.medium_priority)
        priority_layout.addWidget(self.high_priority)
        priority_layout.addStretch()

        layout.addWidget(self.task_input)
        layout.addLayout(priority_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(self.tasks_list)

        add_button.clicked.connect(self.add_task)
        self.task_input.returnPressed.connect(self.add_task)
        delete_button.clicked.connect(self.delete_task)
        clear_completed_task.clicked.connect(self.delete_completed_task)

    def closeEvent(self, event):
        self.client.disconnect_from_server()
        event.accept()

    def get_priority(self):
        if self.high_priority.isChecked():
            return "high"
        elif self.low_priority.isChecked():
            return "low"
        return "medium"

    def add_task(self):
        text = self.task_input.text().strip()
        if text:
            command = {
                "action": "add",
                "text": text,
                "priority": self.get_priority()
            }
            self.client.send_command(command)
            self.task_input.clear()

    def delete_task(self):
        selected_item = self.tasks_list.currentItem()
        if selected_item:
            widget = self.tasks_list.itemWidget(selected_item)
            if widget:
                command = {"action": "delete", "index": widget.index}
                self.client.send_command(command)

    def delete_completed_task(self):
        command = {"action": "clear_completed"}
        self.client.send_command(command)

    def update_completion(self, index, completed):
        command = {"action": "update", "index": index, "completed": completed}
        self.client.send_command(command)


    def update_gui(self, tasks):
        self.current_tasks = tasks
        self.tasks_list.blockSignals(True)
        self.tasks_list.clear()

        for i, task_data in enumerate(tasks):
            text = task_data["text"]
            priority = task_data["priority"]
            completed = task_data["completed"]

            task_widget = TaskWidget(text, priority, completed, i)

            task_widget.completion_changed.connect(self.update_completion)

            item = QListWidgetItem()
            item.setSizeHint(task_widget.sizeHint())
            self.tasks_list.addItem(item)
            self.tasks_list.setItemWidget(item, task_widget)

        self.tasks_list.blockSignals(False)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TaskManager()
    window.show()
    app.exec()