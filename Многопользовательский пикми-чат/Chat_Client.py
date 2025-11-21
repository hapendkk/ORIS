import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, simpledialog

HOST = '127.0.0.1'
PORT = 12345


class ChatClient:
    def __init__(self, master):
        self.master = master
        master.title("Пикми-чатик Питон")
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.client_socket = None
        self.is_connected = False

        self.chat_area = scrolledtext.ScrolledText(master, state='disabled', height=20, width=60, bg='#f9e1f7', fg='#ab274f')
        self.chat_area.pack(padx=10, pady=10)

        self.msg_entry = tk.Entry(master, width=50, bg='#f9e1f7',fg='#ab274f')
        self.msg_entry.bind('<Return>', self.send_message_gui)
        self.msg_entry.pack(padx=10, pady=(0, 5), side=tk.LEFT, fill=tk.X, expand=True)

        self.send_button = tk.Button(master, text="Отправить", command=self.send_message_gui, bg='#f9e1f7',fg='#ab274f',activebackground='#d66b8b')
        self.send_button.pack(padx=(0, 10), pady=(0, 5), side=tk.RIGHT)

        self.menu = tk.Menu(master)
        master.config(menu=self.menu)

        self.connect_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Подключение", menu=self.connect_menu)
        self.connect_menu.add_command(label="Подключиться", command=self.connect_to_server)

        self.room_menu = tk.Menu(self.menu, tearoff=0)
        self.menu.add_cascade(label="Комната", menu=self.room_menu)
        self.room_menu.add_command(label="/join...", command=self.join_room_gui)
        self.room_menu.add_command(label="/leave", command=self.leave_room_gui)
        self.room_menu.add_command(label="/list", command=self.list_rooms_gui)

        self.update_gui_state(False)

    def update_gui_state(self, connected):
        self.is_connected = connected
        state = 'normal' if connected else 'disabled'

        self.msg_entry.config(state=state)
        self.send_button.config(state=state)

        self.room_menu.entryconfig("/join...", state=state)
        self.room_menu.entryconfig("/leave", state=state)
        self.room_menu.entryconfig("/list", state=state)

        self.connect_menu.entryconfig("Подключиться", state='disabled' if connected else 'normal')

    def log(self, message):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, message + '\n')
        self.chat_area.yview(tk.END)  # Прокрутка вниз
        self.chat_area.config(state='disabled')

    def connect_to_server(self):
        if self.is_connected:
            self.log("Уже подключено.")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((HOST, PORT))
            self.log("[ПОДКЛЮЧЕНИЕ] Подключено к серверу.")
            self.update_gui_state(True)
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()

        except ConnectionRefusedError:
            self.log("[ОШИБКА] Не удалось подключиться. Убедитесь, что сервер запущен.")
        except Exception as e:
            self.log(f"[ОШИБКА] Проблема подключения: {e}")

    def receive_messages(self):
        while self.is_connected:
            try:
                data = self.client_socket.recv(1024).decode('utf-8')
                if data:
                    self.log(f"[СЕРВЕР]: {data}")
                else:
                    self.log("[ОТКЛЮЧЕНИЕ] Соединение разорвано сервером.")
                    self.disconnect()
                    break
            except ConnectionResetError:
                self.log("[ОТКЛЮЧЕНИЕ] Соединение разорвано сервером.")
                self.disconnect()
                break
            except OSError:
                #сокет с другого потока закрываеся
                break

    def disconnect(self):
        if self.is_connected:
            try:
                self.client_socket.sendall("exit".encode('utf-8'))
            except Exception:
                pass #даже если закрыт, забъем

            self.client_socket.close()
            self.update_gui_state(False)
            self.log("[ВЫХОД] Вы отключились от сервера.")

    def send_command(self, command):
        if self.is_connected:
            try:
                self.client_socket.sendall(command.encode('utf-8'))
                self.log(f"[КОМАНДА]: {command}")
            except Exception as e:
                self.log(f"[ОШИБКА ОТПРАВКИ]: {e}")
                self.disconnect()

    def send_message_gui(self, event=None):
        message = self.msg_entry.get().strip()
        self.msg_entry.delete(0, tk.END)

        if not message or not self.is_connected:
            return

        if message.startswith('/'):
            self.send_command(message)
        elif message.lower() == 'exit':
            self.disconnect()
        else:
            self.send_command(message)

    def join_room_gui(self):
        room_name = simpledialog.askstring("Присоединиться", "Введите имя комнаты:")
        if room_name:
            self.send_command(f"/join {room_name.strip()}")

    def leave_room_gui(self):
        self.send_command("/leave")

    def list_rooms_gui(self):
        self.send_command("/list")

    def on_closing(self):
        if self.is_connected:
            self.disconnect()
        self.master.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.configure(background='#f7abf0')
    client = ChatClient(root)
    root.mainloop()
