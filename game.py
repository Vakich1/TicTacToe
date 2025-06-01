import pygame
import socket
import threading
import time
import sys

# Настройки окна и игры
WIDTH, HEIGHT = 600, 700
CELL_SIZE = 200
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
LINE_COLOR = (0, 0, 0)
WIN_LINE_COLOR = (255, 0, 0)
LINE_WIDTH = 6
FONT_SIZE = 64
HOST = '127.0.0.1'
PORT = 5000

# Состояние игры
grid = [[None] * 3 for _ in range(3)]
current_player = 'X'
game_over = False
winner = None
my_turn = False
role = None  # 'server', 'client' или None для локальной игры
conn = None
connected = False
running = True
win_line = None

# Реванш
waiting_for_rematch = False  # отправитель ждет
rematch_offered_by_opponent = False  # получатель видит предложение
rematch_accepted = False

# Ошибки
server_error = None  # сообщение об ошибке сервера
error_time = 0

# Режим игры
game_mode = None  # 'network' или 'local'

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Крестики-нолики")
font = pygame.font.SysFont(None, FONT_SIZE)
large_font = pygame.font.SysFont(None, 96)
small_font = pygame.font.SysFont(None, 48)
clock = pygame.time.Clock()


def show_error(msg):
    global server_error, error_time
    server_error = msg
    error_time = time.time()


# Отрисовка меню
def draw_menu():
    screen.fill(WHITE)
    title = large_font.render("Крестики-нолики", True, BLACK)
    screen.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 200)))
    create_text = font.render("Создать игру", True, BLACK)
    connect_text = font.render("Подключиться", True, BLACK)
    local_text = font.render("Локальная игра", True, BLACK)  # Новая кнопка

    create_rect = create_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 120))
    connect_rect = connect_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    local_rect = local_text.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 120))  # Позиция новой кнопки

    pygame.draw.rect(screen, (200, 200, 200), create_rect.inflate(40, 40))
    pygame.draw.rect(screen, (200, 200, 200), connect_rect.inflate(40, 40))
    pygame.draw.rect(screen, (200, 200, 200), local_rect.inflate(40, 40))  # Отрисовка новой кнопки

    screen.blit(create_text, create_rect)
    screen.blit(connect_text, connect_rect)
    screen.blit(local_text, local_rect)  # Отображение текста

    if server_error and time.time() - error_time < 3:
        err = small_font.render(server_error, True, (200, 0, 0))
        screen.blit(err, err.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 200)))

    return create_rect, connect_rect, local_rect  # Возвращаем все три кнопки


# Ожидание подключения
def draw_waiting():
    screen.fill(WHITE)
    text = font.render("Ожидание подключения...", True, BLACK)
    screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
    if server_error and time.time() - error_time < 3:
        err = small_font.render(server_error, True, (200, 0, 0))
        screen.blit(err, err.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 100)))
    pygame.display.flip()


# Отрисовка поля и фигур
def draw_board():
    screen.fill(WHITE)
    for i in range(1, 3):
        pygame.draw.line(screen, LINE_COLOR, (0, i * CELL_SIZE), (WIDTH, i * CELL_SIZE), LINE_WIDTH)
        pygame.draw.line(screen, LINE_COLOR, (i * CELL_SIZE, 0), (i * CELL_SIZE, CELL_SIZE * 3), LINE_WIDTH)
    for y in range(3):
        for x in range(3):
            if grid[y][x]:
                mark = font.render(grid[y][x], True, BLACK)
                screen.blit(mark, mark.get_rect(center=(x * CELL_SIZE + CELL_SIZE // 2,
                                                        y * CELL_SIZE + CELL_SIZE // 2)))
    if win_line:
        pygame.draw.line(screen, WIN_LINE_COLOR, *win_line, LINE_WIDTH + 4)


# Статус хода
def draw_status(msg):
    text = font.render(msg, True, BLACK)
    screen.blit(text, (WIDTH // 2 - text.get_width() // 2, CELL_SIZE * 3 + 20))


# Кнопки и предложение реванша
def draw_rematch_ui():
    rematch_text = small_font.render("Играть снова", True, BLACK)
    exit_text = small_font.render("Выход в меню", True, BLACK)
    rematch_rect = rematch_text.get_rect(center=(WIDTH // 2, HEIGHT - 180))
    exit_rect = exit_text.get_rect(center=(WIDTH // 2, HEIGHT - 120))
    pygame.draw.rect(screen, (200, 200, 200), rematch_rect.inflate(40, 20))
    pygame.draw.rect(screen, (200, 200, 200), exit_rect.inflate(40, 20))
    screen.blit(rematch_text, rematch_rect)
    screen.blit(exit_text, exit_rect)
    if rematch_offered_by_opponent and game_mode == 'network':
        txt = small_font.render("Соперник предлагает реванш", True, BLACK)
        screen.blit(txt, txt.get_rect(center=(WIDTH // 2, HEIGHT - 240)))
    return rematch_rect, exit_rect


# Проверка победы
def check_winner():
    global winner, game_over, win_line
    for i in range(3):
        if grid[i][0] and grid[i][0] == grid[i][1] == grid[i][2]:
            winner = grid[i][0]
            win_line = ((0, i * CELL_SIZE + CELL_SIZE // 2), (WIDTH, i * CELL_SIZE + CELL_SIZE // 2))
            game_over = True
            return
        if grid[0][i] and grid[0][i] == grid[1][i] == grid[2][i]:
            winner = grid[0][i]
            win_line = ((i * CELL_SIZE + CELL_SIZE // 2, 0), (i * CELL_SIZE + CELL_SIZE // 2, CELL_SIZE * 3))
            game_over = True
            return
    if grid[0][0] and grid[0][0] == grid[1][1] == grid[2][2]:
        winner = grid[0][0]
        win_line = ((0, 0), (CELL_SIZE * 3, CELL_SIZE * 3))
        game_over = True
        return
    if grid[0][2] and grid[0][2] == grid[1][1] == grid[2][0]:
        winner = grid[0][2]
        win_line = ((CELL_SIZE * 3, 0), (0, CELL_SIZE * 3))
        game_over = True
        return
    if all(all(cell for cell in row) for row in grid):
        winner = 'Ничья'
        game_over = True


# Сброс игры
def reset():
    global grid, current_player, game_over, winner, my_turn, win_line
    global waiting_for_rematch, rematch_offered_by_opponent, rematch_accepted
    grid = [[None] * 3 for _ in range(3)]
    current_player = 'X'
    game_over = False
    winner = None
    win_line = None
    waiting_for_rematch = False
    rematch_offered_by_opponent = False
    rematch_accepted = False

    # Для сетевой игры устанавливаем чей ход в зависимости от роли
    if game_mode == 'network':
        my_turn = (role == 'server')
    else:
        # Для локальной игры всегда начинает первый игрок
        my_turn = True


# Сетевая часть
def handle_network():
    global conn, connected, my_turn, server_error
    if role == 'server':
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, PORT))
            s.listen(1)
            s.settimeout(0.5)
            while running and not connected:
                try:
                    conn, _ = s.accept()
                    connected = True
                    my_turn = True
                except socket.timeout:
                    continue
                except OSError as e:
                    show_error(f"Ошибка сервера: {e}")
                    break
        except OSError as e:
            show_error("Не удалось создать сервер (уже запущен?)")
    else:
        s = socket.socket()
        while not connected and running:
            try:
                s.connect((HOST, PORT))
                conn = s
                connected = True
                my_turn = False
            except ConnectionRefusedError:
                time.sleep(1)
            except Exception as e:
                show_error(f"Ошибка подключения: {e}")
                break


def send_move(x, y):
    if conn:
        try:
            conn.send(f"move:{x},{y}".encode())
        except:
            show_error("Ошибка отправки хода")


def send_rematch_request():
    if conn:
        try:
            conn.send("rematch:request".encode())
        except:
            show_error("Ошибка запроса реванша")


def send_rematch_response(accepted):
    if conn:
        try:
            conn.send(f"rematch:{'accept' if accepted else 'reject'}".encode())
        except:
            show_error("Ошибка ответа на реванш")


def send_exit():
    if conn:
        try:
            conn.send("exit".encode())
        except:
            pass


def return_to_menu():
    global state, connected, conn, waiting_for_rematch, rematch_offered_by_opponent, game_mode
    if game_mode == 'network':
        send_exit()
    state = 'menu'
    connected = False
    if conn:
        conn.close()
    conn = None
    waiting_for_rematch = False
    rematch_offered_by_opponent = False
    game_mode = None
    reset()


# Поток приема
def receive_moves():
    global my_turn, waiting_for_rematch, rematch_offered_by_opponent, rematch_accepted, running, state, connected, conn
    while running:
        if connected and conn:
            try:
                data = conn.recv(1024).decode()
                if not data:
                    show_error("Соединение разорвано")
                    return_to_menu()
                    continue

                if data.startswith("move:"):
                    x, y = map(int, data[5:].split(','))
                    if not grid[y][x]:
                        grid[y][x] = 'O' if current_player == 'X' else 'X'
                        my_turn = True
                        check_winner()
                elif data == "rematch:request":
                    waiting_for_rematch = False
                    rematch_offered_by_opponent = True
                elif data == "rematch:accept":
                    rematch_accepted = True
                    reset()
                elif data == "rematch:reject":
                    waiting_for_rematch = False
                    rematch_offered_by_opponent = False
                    show_error("Соперник отказал в реванше")
                elif data == "exit":
                    show_error("Соперник вышел из игры")
                    return_to_menu()
            except Exception as e:
                return_to_menu()
        time.sleep(0.1)


# Основная функция
def main():
    global role, my_turn, current_player, running, waiting_for_rematch, rematch_offered_by_opponent, rematch_accepted, state, connected, conn, server_error, game_mode

    state = 'menu'
    create_button, connect_button, local_button = draw_menu()
    pygame.display.flip()

    # Запускаем поток для приема сообщений
    recv_thread = threading.Thread(target=receive_moves, daemon=True)
    recv_thread.start()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                if conn:
                    send_exit()
                    conn.close()
                break

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if state == 'menu':
                    server_error = None  # Сбрасываем ошибку при новом выборе
                    if create_button.collidepoint(event.pos):
                        role = 'server'
                        game_mode = 'network'
                        draw_waiting()
                        pygame.display.flip()
                        # Запускаем сервер в отдельном потоке
                        server_thread = threading.Thread(target=handle_network, daemon=True)
                        server_thread.start()
                        # Ждем подключения или ошибки
                        start_time = time.time()
                        while not connected and not server_error and time.time() - start_time < 10 and running:
                            time.sleep(0.1)
                            draw_waiting()
                            pygame.display.flip()

                        if connected:
                            state = 'game'
                            reset()
                            time.sleep(0.5)  # Даем время для синхронизации
                        elif server_error:
                            state = 'menu'

                    elif connect_button.collidepoint(event.pos):
                        role = 'client'
                        game_mode = 'network'
                        draw_waiting()
                        pygame.display.flip()
                        # Пытаемся подключиться
                        connect_thread = threading.Thread(target=handle_network, daemon=True)
                        connect_thread.start()
                        # Ждем подключения или ошибки
                        start_time = time.time()
                        while not connected and not server_error and time.time() - start_time < 5 and running:
                            time.sleep(0.1)
                            draw_waiting()
                            pygame.display.flip()

                        if connected:
                            state = 'game'
                            reset()
                            time.sleep(0.5)  # Даем время для синхронизации
                        elif server_error:
                            state = 'menu'

                    elif local_button.collidepoint(event.pos):
                        game_mode = 'local'
                        state = 'game'
                        reset()

                elif state == 'game' and not game_over:
                    # Обработка хода только если:
                    # - В сетевом режиме и наш ход
                    # - В локальном режиме всегда
                    if game_mode == 'local' or (game_mode == 'network' and my_turn):
                        x, y = event.pos[0] // CELL_SIZE, event.pos[1] // CELL_SIZE
                        if 0 <= x < 3 and 0 <= y < 3 and not grid[y][x]:
                            grid[y][x] = current_player

                            # В локальном режиме сразу меняем игрока
                            if game_mode == 'local':
                                # Меняем игрока после хода
                                current_player = 'O' if current_player == 'X' else 'X'

                            # В сетевом режиме отправляем ход
                            if game_mode == 'network':
                                send_move(x, y)

                            check_winner()

                            # В сетевом режиме передаем ход
                            if game_mode == 'network':
                                my_turn = False

                elif state == 'game' and game_over:
                    rematch_rect, exit_rect = draw_rematch_ui()
                    if rematch_rect.collidepoint(event.pos):
                        if game_mode == 'network':
                            if not waiting_for_rematch and not rematch_offered_by_opponent:
                                send_rematch_request()
                                waiting_for_rematch = True
                            elif rematch_offered_by_opponent:
                                send_rematch_response(True)
                                rematch_accepted = True
                                reset()
                        else:  # Локальный режим
                            reset()
                    elif exit_rect.collidepoint(event.pos):
                        if game_mode == 'network' and rematch_offered_by_opponent:
                            send_rematch_response(False)
                        return_to_menu()

        # Отрисовка текущего состояния
        screen.fill(WHITE)
        if state == 'menu':
            create_button, connect_button, local_button = draw_menu()
        elif state == 'game':
            draw_board()
            if not game_over:
                if game_mode == 'local':
                    # Для локальной игры показываем, чей сейчас ход
                    status_text = "Ход крестиков" if current_player == 'X' else "Ход ноликов"
                    draw_status(status_text)
                else:  # Сетевой режим
                    draw_status("Ваш ход" if my_turn else "Ход соперника")
            else:
                # Формируем текст результата в зависимости от режима
                if game_mode == 'local':
                    if winner == 'X':
                        result_text = "Победили крестики!"
                    elif winner == 'O':
                        result_text = "Победили нолики!"
                    else:
                        result_text = "Ничья!"
                else:
                    if winner == current_player:
                        result_text = "Вы выиграли!"
                    elif winner == 'Ничья':
                        result_text = "Ничья!"
                    else:
                        result_text = "Вы проиграли!"

                draw_status(result_text)
                rematch_rect, exit_rect = draw_rematch_ui()

                if game_mode == 'network':
                    if waiting_for_rematch and not rematch_offered_by_opponent:
                        txt = small_font.render("Ожидание ответа...", True, BLACK)
                        screen.blit(txt, txt.get_rect(center=(WIDTH // 2, HEIGHT - 240)))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()
    sys.exit()


if __name__ == '__main__':
    main()