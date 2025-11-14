#прописать сервак, исходный таск апнуть до клиента
import socket
import threading
import json
import sys

HOST = '127.0.0.1'
PORT = 65432
BUFFER_SIZE = 1024

tasks = []
clients = []
tasks_lock = threading.Lock()


def tasks_mailing():
    task_list = {"action": "list_update", "tasks": tasks}
    message = json.dumps(task_list) + '\n'

    with tasks_lock:
        finished_clients = []
        for client_socket in clients:
            try:
                client_socket.sendall(message.encode('utf-8'))
            except Exception as e:
                print(f"Ошибка при рассылке клиенту {client_socket.getpeername()}: {e}")
                finished_clients.append(client_socket)

        for client_socket in finished_clients:
            clients.remove(client_socket)
            print(f"Клиент {client_socket.getpeername()} отключен и удален из списка.")


def client_processing(conn, addr):
    print(f"Подключен клиент: {addr}")
    tasks_mailing()

    while True:
        try:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break

            messages = data.decode('utf-8').strip().split('\n')

            for m in messages:
                if not m:
                    continue

                command = json.loads(m)
                action = command.get("action")

                print(f"Получена команда от {addr}: {action}")

                with tasks_lock:
                    if action == "add":
                        new_task = {
                            "text": command["text"],
                            "priority": command["priority"],
                            "completed": False
                        }
                        tasks.append(new_task)

                    elif action == "delete":
                        index = command.get("index")
                        if index is not None and 0 <= index < len(tasks):
                            tasks.pop(index)

                    elif action == "clear_completed":
                        for i in range(len(tasks) - 1, -1, -1):
                            if tasks[i]["completed"]:
                                tasks.pop(i)

                    elif action == "update":
                        index = command.get("index")
                        completed = command.get("completed")
                        if index is not None and 0 <= index < len(tasks):
                            tasks[index]["completed"] = completed

                tasks_mailing()

        except ConnectionResetError:
            break
        except json.JSONDecodeError:
            print(f"Ошибка JSON от {addr}")
        except Exception as e:
            print(f"Непредвиденная ошибка при обработке клиента {addr}: {e}")
            break

    with tasks_lock:
        if conn in clients:
            clients.remove(conn)

    conn.close()
    print(f"Соединение с клиентом {addr} закрыто.")


def start_server():
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"Сервер запущен и слушает на {HOST}:{PORT}")
    except Exception as e:
        print(f"Не удалось запустить сервер: {e}")
        sys.exit(1)

    while True:
        try:
            conn, addr = server_socket.accept()
            with tasks_lock:
                clients.append(conn)

            client_thread = threading.Thread(target=client_processing, args=(conn, addr))
            client_thread.daemon = True
            client_thread.start()
        except KeyboardInterrupt:
            print("\nСервер остановлен пользователем.")
            break
        except Exception as e:
            print(f"Ошибка при приеме соединения: {e}")
            continue

    server_socket.close()


if __name__ == '__main__':
    start_server()