import socket
import threading
import os

# у нас будет два потока:
# первый поток (наш основной поток) - ввода команд пользователем
# второй поток (мы его создали дополнительно) - прием сообщений от сервера и отображение доски, чата и результатов игры

HOST = '127.0.0.1'
PORT = 12346


def display_board(board_str):
    if len(board_str) != 9:
        print("Ошибка формата доски")
        return

    print("\n" + "═" * 25)
    print("    КРЕСТИКИ-НОЛИКИ")
    print("═" * 25)
    print("     1   2   3")
    print("   ┌───┬───┬───┐")

    for i in range(3):
        row_label = chr(65 + i)
        row_start = i * 3
        row_cells = board_str[row_start:row_start + 3]

        display_cells = [cell if cell != ' ' else ' ' for cell in row_cells]
        print(f" {row_label} │ {display_cells[0]} │ {display_cells[1]} │ {display_cells[2]} │")

        if i < 2:
            print("   ├───┼───┼───┤")

    print("   └───┴───┴───┘")
    print("═" * 25)


def convert_move(move_str):
    if len(move_str) != 2:
        return None

    letter = move_str[0].upper()
    digit = move_str[1]

    if letter not in ['A', 'B', 'C']:
        return None
    if digit not in ['1', '2', '3']:
        return None

    row = ord(letter) - ord('A')
    col = int(digit) - 1

    return row * 3 + col


# функция для приёма сообщений от сервера
def receive_messages(sock):
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                print("[ОТКЛЮЧЕНИЕ] Сервер закрыл соединение")
                break

            # TODO: Обработка сообщений от сервера
            # 1) BOARD <данные> - обновление доски и вывод в консоль
            if data.startswith('BOARD'):
                board_data = data[6:]
                display_board(board_data)
            # 2) TURN <X/O> - информация о том, чей сейчас ход
            elif data.startswith('TURN'):
                turn = data[5:]
                print(f'Сейчас ход: {turn}')
            # 3) CHAT <сообщение> - вывод сообщения соперника
            elif data.startswith('CHAT'):
                message = data[5:]
                print(message)
            # 4) WIN/DRAW - вывод результата игры
            elif data.startswith('WIN'):
                winner = data[4:]
                print(f'ПОБЕДА! Выиграл {winner} XD')
                print('Игра завершена!')

            elif data == 'DRAW':
                print('НИЧЬЯ! Игра завершена')
            # 5) OPPONENT <имя> - информация о сопернике
            elif data.startswith('OPPONENT'):
                opponent = data[9:]
                print(f"Ваш противник: {opponent}")
            elif data.startswith('OPPONENT_DISCONNECT'):
                print("ПРОТИВНИК ОТКЛЮЧИЛСЯ! Игра завершена.")
            elif data.startswith("SYMBOL"):
                symbol = data[7:]
                print(f"Вы играете за: {symbol}")
            elif data.startswith("WAITING"):
                message = data[8:]
                print(message)
            elif data.startswith("ERROR"):
                error = data[6:]
                print(f"Ошибка: {error}")
            else:
                print(f"Сервер: {data}")

            print("\nВведите команду (MOVE, CHAT, STATUS, exit): ", end="", flush=True)

        except ConnectionResetError:
            print("\n[ОТКЛЮЧЕНИЕ] Соединение разорвано сервером")
            break
        except Exception as e:
            print(f"\n[ОШИБКА] Произошла ошибка: {e}")
            break


# основная функция клиента
def start_client():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with client_socket:
        client_socket.connect((HOST, PORT))
        print("[ПОДКЛЮЧЕНИЕ] Подключено к серверу")
        print("Пришли поиграть в крестики-нолики вместо учебы???")
        print("ДОБРО ПОЖАЛОВАТЬ!!!")

        # поток для приёма сообщений от сервера
        threading.Thread(target=receive_messages, args=(client_socket,), daemon=True).start()

        # основной поток для ввода команд пользователем
        while True:
            try:
                command = input("Введите команду (MOVE, CHAT, STATUS, exit): ").strip()
                if command.lower() == "exit":
                    client_socket.sendall("exit".encode('utf-8'))
                    print("[ВЫХОД] Вы отключились от сервера")
                    break

                # TODO: Можно добавить валидацию команд (но вы сами понимаете, что не факт, что оно вам нужно будет)
                # MOVE <клетка>, CHAT <сообщение>, STATUS
                if not command:
                    continue

                # Обработка хода в формате буква+цифра
                if command.upper().startswith("MOVE "):
                    move_str = command[5:].strip().upper()
                    position = convert_move(move_str)

                    if position is None:
                        print("Ошибка: Неверный формат хода! Используйте: MOVE A1, MOVE B2, MOVE C3")
                        continue

                    client_socket.sendall(f"MOVE {position}".encode('utf-8'))
                else:
                    client_socket.sendall(command.encode('utf-8'))

            except KeyboardInterrupt:
                print("[ПРЕРВАНО] Завершаем работу...")
                client_socket.sendall("exit".encode('utf-8'))
                break
            except Exception as e:
                print(f"[ОШИБКА] Не удалось отправить команду: {e}")
                break


if __name__ == "__main__":
    start_client()