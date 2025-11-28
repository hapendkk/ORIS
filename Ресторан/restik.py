import threading
import queue
import time
from datetime import datetime
import random

kitchen_ready = threading.Event()
order_queue = queue.Queue(maxsize=10)
stove_condition = threading.Condition()
ready_stoves = 2

stats_lock = threading.Lock()

menu = {
    "Павлова с ягодами": 2,
    "Граните из шампанского": 4,
    "Творожные вафли": 1,
    "Сабайон с вишней и амаретти": 5,
    "Тарт с клубникой": 3,
    "Меренговый рулет": 2,
    "Тирамису с трюфелем": 4
}

total_orders = 0
completed_orders = 0
total_cooking_time = 0
order_status = {}

class Order:
    def __init__(self, order_id, meals):
        self.order_id = order_id
        self.meals = meals
        self.status = "ожидает"
        self.start_time = None
        self.end_time = None

def kitchen_prepare():
    print("--Подготовка кухни -- 1%")
    time.sleep(2)
    print("-- Кухня готова -- 100%")
    kitchen_ready.set() #горит фонарик с готвностью

def order_producer(waiter_id):
    global total_orders
    print(f"Официант {waiter_id} ждет готовности кухни")
    kitchen_ready.wait()
    print(f"Официант {waiter_id} начал работать")

    for i in range(2):
        time.sleep(random.uniform(1,3))
        amount_of_meals = random.randint(1,3)
        meals = random.sample(list(menu.items()), amount_of_meals)

        with stats_lock:
            total_orders += 1
            order_id = total_orders

        order = Order(order_id, meals)
        order_status[order_id] = order

        meal_names = [meal[0] for meal in meals]
        print(f"Официант {waiter_id} создал заказ №{order_id}: {meal_names}")

        try:
            order_queue.put(order, block = True, timeout = 3)
            print(f"Заказ №{order_id} добавлен в очередь")
        except queue.Full:
            print(f"Заказов слишком много. Заказ №{order_id} - отменён")

def chef_consumer(chef_id):
    global total_cooking_time, completed_orders, ready_stoves, total_orders
    print("Ресторан ждет открытия...")
    kitchen_ready.wait()
    print(f"Ресторан открыт! Шэф {chef_id} начал готовить")

    start_time = time.time()

    while time.time() - start_time < 30:
        with stats_lock:
            if total_orders > 0 and completed_orders >= total_orders and order_queue.empty():
                print(f"Шеф {chef_id}: все заказы обработаны, завершаю работу")
                break

        try:
            order = order_queue.get(block = True, timeout = 8)
            order.status = "готовится"
            order.start_time = time.time()

            print(f"Шэф {chef_id} готовит заказ №{order.order_id}")
            for meal_name, difficulty in order.meals:
                with stove_condition:
                    while ready_stoves == 0:
                        print(f"Шэф {chef_id} ждет свободную конфорку для {meal_name}...")
                        if not stove_condition.wait(timeout=3):
                            if ready_stoves == 0:
                                continue

                    ready_stoves -= 1
                    print(f"Конфорка занята для {meal_name}. Осталось конфорок: {ready_stoves}")

                cooking_time = difficulty * 0.5
                print(f"Шэф готовит {meal_name} - {cooking_time} мин") #для правдоподобности в тексте написла про минуты
                time.sleep(cooking_time)

                with stove_condition:
                    ready_stoves += 1
                    print(f"Конфорка свободна. Всего свободных: {ready_stoves}")
                    stove_condition.notify_all()

            order.end_time = time.time()
            order.status = "готов"
            cooking_duration = order.end_time - order.start_time
            with stats_lock:
                total_cooking_time += cooking_duration
                completed_orders += 1

            print(f"Шэф {chef_id} приготовил заказ №{order.order_id}. Время приготовления: {cooking_duration:.2f} мин")

            order_queue.task_done()

        except queue.Empty:
            break

def monitoring():
    print("[СИСТЕМА] Текущее состояние ресторана---")
    with open("restik_monitoring.log", "w", encoding="utf-8") as f:
        f.write("---Мониторинг данных ресторана---\n")

    while True:
        time.sleep(5)
        timing = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with stats_lock:
            orders_in_queue = order_queue.qsize()
            current_total_orders = total_orders
            current_completed_orders = completed_orders
            current_total_cooking_time = total_cooking_time

        with stove_condition:
            current_ready_stoves = ready_stoves

        mid_cook_time = 0
        if current_completed_orders > 0:
            mid_cook_time = current_total_cooking_time / current_completed_orders

        with open("restik_monitoring.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{timing}]\n")
            f.write(f"Всего заказов: {total_orders}\n")
            f.write(f"Выполнено заказов: {completed_orders}\n")
            f.write(f"Заказов в очереди: {orders_in_queue}\n")
            f.write(f"Среднее время приготовления: {mid_cook_time:.2f} мин\n")
            f.write(f"Свободные конфорки: {ready_stoves}/2\n")
            f.write("-" * 40 + "\n")


def main():
    print('---Система ресторана "Fée du sucre" приветствует Вас!---')
    kitchen_thread = threading.Thread(target=kitchen_prepare)
    kitchen_thread.start()

    monitoring_thread = threading.Thread(target=monitoring, daemon = True)
    monitoring_thread.start()

    waiters = []
    for i in range(3):
        waiter = threading.Thread(target=order_producer, args=(i + 1,))
        waiters.append(waiter)
        waiter.start()

    chefs = []
    for i in range(2):
        chef = threading.Thread(target=chef_consumer, args=(i + 1,))
        chefs.append(chef)
        chef.start()

    for waiter in waiters:
        waiter.join()

    for chef in chefs:
        chef.join(timeout=10)

    order_queue.join()
    time.sleep(2)

    with stats_lock:
        final_completed_orders = completed_orders
        final_total_orders = total_orders

    print('\n---Ресторан "Fée du sucre" закрывается')
    print(f"Итоги: обработано {completed_orders} из {total_orders} заказов")
    print("Статистика сохранена в файл restik_monitoring.log")

if __name__ == "__main__":
    main()
