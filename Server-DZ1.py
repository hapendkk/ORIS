import socket
import threading

HOST = '127.0.0.1'
PORT = 12346

clients = []  # список подключенных клиентов
clients_lock = threading.Lock()  # сразу приготовили lock для того, чтобы изменять список АКТИВНЫХ клиентов
games = {}  # словарь для хранения игр: {player_name: {"opponent": opponent_name, "board": [...], "turn": "X"}}
games_lock = threading.Lock()

# функция для отправки сообщения клиенту
def send_message(client, message):
    try:
        client.sendall(message.encode('utf-8'))
    except (ConnectionResetError, BrokenPipeError):
        print(f"[ОШИБКА] Не удалось отправить сообщение клиенту {client}")

def board_full(game):
    return ' ' not in game['board']

def who_wins(game):
    board = game['board']
    winning_poses = [
        [0,1,2],[3,4,5],[6,7,8], # эт по горизонтали
        [0,3,6],[1,4,7],[2,5,8], #а это по вертикали
        [0,4,8],[2,4,6] # а тут вообще диагональ Q_Q
    ]

    for line in winning_poses:
        a, b, c = line
        if board[a] != ' ' and board[a] == board[b] == board[c]:
            return board[a]

    return None

def current_status(game):
    board_str = ''.join(game['board'])
    board_message = f'BOARD {board_str}'
    turn_message = f"TURN {game['current_player']}"

    if game['player_x']:
        send_message(game['player_x'], board_message)
        send_message(game['player_x'], turn_message)

    if game['player_o']:
        send_message(game['player_o'], board_message)
        send_message(game['player_o'], turn_message)

def handle_client(conn, addr):
    print(f"[НОВОЕ ПОДКЛЮЧЕНИЕ] {addr}")
    with clients_lock:
        clients.append(conn)  # добавляем клиента в общий список

    player_name = f"Player{addr[1]}"
    player_symbol = None
    game = None
    game_id = None

    try:
        with (games_lock):
            found_game = False

            for current_game_id, current_game in games.items():
                if current_game['waiting_player']:
                    game = current_game
                    game_id = current_game_id

                    if game['player_x'] is None:
                        game['player_x'] = conn
                        game['player_x_name'] = player_name
                        player_symbol = "X"
                    else:
                        game['player_o'] = conn
                        game['player_o_name'] = player_name
                        player_symbol = "O"

                    game['waiting_player'] = False
                    found_game = True
                    break

            if not found_game:
                game_id = f"game_{addr[1]}"
                game = {
                    'player_x': conn,
                    'player_o': None,
                    'board': [' ']*9,
                    'current_player': 'X',
                    'waiting_player': True
                }
                games[game_id] = game
                player_symbol = 'X'

                send_message(conn, 'WAITING Ожидаем подключения второго игрока...')
                print(f'[ИГРА СОЗДАНА] {game_id} ждет второго игрока :)')

        if found_game:
            if conn == game['player_x']:
                opponent_name = game.get('player_o_name', 'unknown')
                opponent_conn = game['player_o']
            else:
                opponent_name = game.get('player_x_name', 'unknown')
                opponent_conn = game['player_x']

            send_message(conn, f'OPPONENT {opponent_name}')
            send_message(conn, f'SYMBOL {player_symbol}')

            if opponent_conn:
                send_message(opponent_conn, f'OPPONENT {player_name}')
                send_message(opponent_conn, f'SYMBOL {"O" if player_symbol == "X" else "X"}')

                current_status(game)
                print(f'[ИГРА НАЧАЛАСЬ] {game_id}. {player_name} ПРОТИВ {opponent_name}')


        while True:
            data = conn.recv(1024).decode('utf-8')

            if not data:
                print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} закрыл соединение")
                break

            # TODO: Обработка команд от клиента
            # 1) MOVE <клетка> - обновление доски, проверка хода, отправка BOARD/TURN/WIN/DRAW
            # 2) CHAT <сообщение> - отправка сообщения сопернику
            # 3) STATUS - отправка текущей доски и информации о ходе

            if data.startswith("MOVE"):
                try:
                    position = int(data.split()[1])
                    with games_lock:
                        game = games.get(game_id)

                        if game and not game['waiting_player']:
                            current_player_conn = game['player_x'] if game['current_player'] == 'X' else game['player_o']

                            if conn !=  current_player_conn:
                                send_message(conn, f'ERROR Сейчас не ваш ход, ждите хода соперника')
                                continue

                            #можно ли сделать ход
                            if 0 <= position < 9 and game["board"][position] == ' ':
                                game['board'][position] = player_symbol

                                winner = who_wins(game)
                                if winner:
                                    send_message(game['player_x'], f'WIN {winner}')
                                    send_message(game['player_o'], f'WIN {winner}')
                                    print(f'[ИГРА ЗАВЕРШЕНА] {game_id} - победитель: {winner}')

                                    del games[game_id]
                                    break

                                elif board_full(game):
                                    send_message(game['player_x'], f'DRAW')
                                    send_message(game['player_o'], f'DRAW')
                                    print(f'[ИГРА ЗАВЕРШЕНА] {game_id} - ничья!')

                                    del games[game_id]
                                    break

                                else:
                                    game['current_player'] = 'O' if game['current_player'] == 'X' else 'X'
                                    current_status(game)
                            else:
                                send_message(conn, f'ERROR Сюда нельзя сходить, клетка занята или ваша позиция неверна')

                except(IndexError, ValueError):
                    send_message(conn, f'ERROR Неверный формат ввода команды MOVE (0-8)')

            elif data.startswith("CHAT"):
                try:
                    message = data[5:].strip()

                    with games_lock:
                        game = games.get(game_id)

                        if game and not game['waiting_player']:
                            if conn == game['player_x']:
                                receiver = game['player_o']
                            else:
                                receiver = game['player_x']

                            if receiver:
                                send_message(receiver, f'CHAT {player_name}: {message}')
                            else:
                                send_message(conn, f'ERROR Нет подключенного противника')

                        else:
                            send_message(conn, "ERROR Ожидаем подключения противника")

                except Exception as e:
                    send_message(conn, 'ERROR Ошибка отправки сообщения')

            elif data.startswith("STATUS"):
                with games_lock:
                    game = games.get(game_id)

                    if game:
                        board_str = ''.join(game['board'])
                        send_message(conn, f'BOARD {board_str}')
                        send_message(conn, f'TURN {game["current_player"]}')
                    else:
                        send_message(conn, f'ERROR Игра не найдена')

            elif data.lower() == "exit":
                print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} вышел из игры")
                break
            else:
                send_message(conn, "ERROR Неизвестная команда (MOVE, CHAT, STATUS, exit)")
    except ConnectionResetError:
        print(f"[ОТКЛЮЧЕНИЕ] Клиент {addr} отключился некорректно")
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
        # TODO: при выходе игрока - уведомить соперника и удалить игру из games
        if game_id:
            with games_lock:
                game = games.get(game_id)
                if game:
                    if game['player_x'] == conn and game['player_o']:
                        send_message(game['player_o'], f'OPPONENT_DISCONNECT Соперник отключился')

                    elif game["player_o"] == conn and game["player_x"]:
                        send_message(game["player_x"], "OPPONENT_DISCONNECT Соперник отключился")

                    if game_id in games:
                        del games[game_id]
                        print(f'[ИГРА УДАЛЕНА] {game_id}')
        conn.close()

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    with server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"[СЕРВЕР ЗАПУЩЕН] {HOST}:{PORT}")
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.start()

if __name__ == "__main__":
    start_server()