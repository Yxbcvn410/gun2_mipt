import copy
import json
import math
import os
import tkinter as tk
from abc import ABC, abstractmethod
from random import choice, randint as rnd
from tkinter import filedialog, messagebox

import hit_check

# Time step for delayed jobs
DT = 30
VICTORY_MSG_TIME = 3000
WINDOW_SHAPE = (800, 600)
MARGIN = 100


def pass_event(event):
    pass


class Agent(ABC):
    def __init__(self):
        self.job = None

    @abstractmethod
    def start(self):
        self.job = self.canvas.after(DT, self.update)

    @abstractmethod
    def play(self):
        if self.job == 'pause':
            self.job = self.canvas.after(DT, self.update)

    @abstractmethod
    def stop(self):
        if self.job is not None:
            self.canvas.after_cancel(self.job)
            self.job = None

    @abstractmethod
    def pause(self):
        if self.job is not None and self.job != 'pause':
            self.canvas.after_cancel(self.job)
            self.job = 'pause'

    @abstractmethod
    def update(self):
        pass


class Ball(Agent):
    def __init__(
            self,
            canvas,
            x,
            y,
            vx,
            vy,
            color=None,
            live=None,
            job_init=None,
            job_explosion=None
    ):
        super().__init__()
        self.job = job_init
        self.explosion_job = job_explosion
        self.explosion_level = 0

        self.canvas = canvas
        self.x = x
        self.y = y
        self.r = 10
        self.jumpiness = 0.7
        self.stop_v = 3
        self.vx = vx
        self.vy = vy
        if color is None:
            self.color = choice(['blue', 'green', 'red', 'brown'])
        else:
            self.color = color

        self.id = self.canvas.create_oval(
            self.x - self.r,
            self.y - self.r,
            self.x + self.r,
            self.y + self.r,
            fill=self.color
        )

        self.live = 100 if live is None else live
        self.canvas.bullets[self.id] = self
        # Используется для определения номера выстрела, которым уничтожена
        # цель.
        self.bullet_number = self.canvas.get_bullet_number()

    def start(self):
        super().start()

    def play(self):
        super().play()
        if self.explosion_job == 'pause':
            self.explosion_job = self.canvas.after(DT, self.destroy)

    def stop(self):
        super().stop()

    def pause(self):
        super().pause()
        if self.explosion_job is not None and self.explosion_job != 'pause':
            self.canvas.after_cancel(self.explosion_job)
            self.explosion_job = 'pause'

    def update(self):
        self.x += self.vx
        self.y -= self.vy
        self.vy -= 1.6
        self.set_coords()
        if (self.vx ** 2 + self.vy ** 2 < self.stop_v ** 2) and (WINDOW_SHAPE[1] - MARGIN - self.y < 5):
            self.destroy()
            return
        self.hit_targets()
        if self.x < MARGIN:
            self.vx *= -self.jumpiness
            self.vy *= self.jumpiness
            self.x = 2 * MARGIN - self.x
        if self.x > WINDOW_SHAPE[0] - MARGIN:
            self.vx *= -self.jumpiness
            self.vy *= self.jumpiness
            self.x = 2 * (WINDOW_SHAPE[0] - MARGIN) - self.x
        if self.y > WINDOW_SHAPE[1] - MARGIN:
            self.vx *= self.jumpiness
            self.vy += 1.8
            self.vy *= -self.jumpiness
            if abs(self.vy) < self.stop_v:
                self.vy = 0
            self.y = 2 * (WINDOW_SHAPE[1] - MARGIN) - self.y
        self.job = self.canvas.after(DT, self.update)

    def destroy(self):
        if self.explosion_level == 0:
            del self.canvas.bullets[self.id]
            self.color = 'yellow'
        if self.explosion_level < 7:
            self.r = 4.6 * self.explosion_level
            self.y -= 3.6
            self.set_coords()
            self.explosion_level += 1
            self.explosion_job = self.canvas.after(DT, self.destroy)
            return
        self.explosion_job = None
        self.stop()
        self.canvas.delete(self.id)

    def set_coords(self):
        self.canvas.coords(
            self.id,
            self.x - self.r,
            self.y - self.r,
            self.x + self.r,
            self.y + self.r
        )
        self.canvas.itemconfig(self.id, fill=self.color)

    def hit_targets(self):
        ids_hit = []
        for t_id, t in list(self.canvas.targets.items()):
            if hit_check.is_hit(
                    (self.x, self.y),
                    self.r,
                    (-self.vx, -self.vy),
                    (t.x, t.y),
                    t.r
            ):
                self.canvas.report_hit(self, t)
                ids_hit.append(t_id)
                t.destroy()
        return ids_hit

    def get_state(self):
        state = {
            'x': self.x,
            'y': self.y,
            'vx': self.vx,
            'vy': self.vy,
            'color': self.color,
            'live': self.live,
            'job': self.job is not None,
            'job_explosion': self.explosion_job is not None
        }
        return state


class Gun(Agent):
    def __init__(self, canvas):
        super().__init__()

        self.gun_velocity = 1
        self.gun_power_gain = 1
        self.min_gun_power = 10
        self.max_gun_power = 70
        self.zero_power_length = 20

        self.gun_coords = [MARGIN + 20, WINDOW_SHAPE[1] * 0.66]
        self.vy = 0
        self.mouse_coords = [None, None]
        self.f2_power = 10
        self.f2_on = 0
        self.an = 1

        self.canvas = canvas
        self.id = self.canvas.create_line(
            *self.gun_coords, *self.get_gunpoint(), width=7)

        self.job = None

    def start(self):
        self.bind_all()
        super().start()

    def play(self):
        if self.job == 'pause':
            self.bind_all()
        super().play()

    def stop(self):
        super().stop()
        self.unbind_all()
        self.vy = 0
        self.f2_power = 10
        self.f2_on = 0
        self.mouse_coords = [None, None]

    def pause(self):
        super().pause()
        self.unbind_all()
        self.mouse_coords = [None, None]

    def update(self):
        if self.f2_on and (self.f2_power < self.max_gun_power):
            self.f2_power += self.gun_power_gain
        self.update_angle()
        self.redraw()
        self.job = self.canvas.after(DT, self.update)

    def update_angle(self):
        self.mouse_coords = self.canvas.get_mouse_coords()
        dx = self.mouse_coords[0] - self.gun_coords[0]
        dy = self.mouse_coords[1] - self.gun_coords[1]
        if dx != 0:
            self.an = math.atan(dy / dx)
        else:
            self.an = 1

    def get_gunpoint(self):
        length = self.f2_power + self.zero_power_length
        x = self.gun_coords[0] + length * math.cos(self.an)
        y = self.gun_coords[1] + length * math.sin(self.an)
        return x, y

    def redraw(self):
        self.canvas.coords(self.id, *self.gun_coords, *self.get_gunpoint())
        if self.f2_on:
            self.canvas.itemconfig(self.id, fill='orange')
        else:
            self.canvas.itemconfig(self.id, fill='black')

    def fire2_start(self, event):
        self.f2_on = 1

    def fire2_end(self, event):
        self.f2_on = 0
        b = Ball(self.canvas, *self.gun_coords, self.f2_power * math.cos(self.an), - self.f2_power * math.sin(self.an))
        b.start()
        self.f2_power = self.min_gun_power

    def set_movement_direction_to_up(self, event):
        self.vy = -self.gun_velocity

    def set_movement_direction_to_down(self, event):
        self.vy = self.gun_velocity

    def stop_movement(self, event):
        self.vy = 0

    def bind_all(self):
        self.canvas.bind('<Button-1>', self.fire2_start, add='')
        self.canvas.bind('<ButtonRelease-1>', self.fire2_end, add='')

        root = self.canvas.get_root()
        root.bind('<Up>', self.set_movement_direction_to_up, add='')
        root.bind('<KeyRelease-Up>', self.stop_movement, add='')
        root.bind('<Down>', self.set_movement_direction_to_down, add='')
        root.bind('<KeyRelease-Down>', self.stop_movement, add='')

    def unbind_all(self):
        self.canvas.bind('<Button-1>', pass_event, add='')
        self.canvas.bind('<ButtonRelease-1>', pass_event, add='')
        root = self.canvas.get_root()
        root.bind('<Up>', pass_event, add='')
        root.bind('<KeyRelease-Up>', pass_event, add='')
        root.bind('<Down>', pass_event, add='')
        root.bind('<KeyRelease-Down>', pass_event, add='')

    def get_state(self):
        state = {
            'gun_coords': self.gun_coords,
            'vy': self.vy,
            'f2_power': self.f2_power,
            'f2_on': self.f2_on,
            'an': self.an,
            'job': self.job is not None
        }
        return state

    def set_state(self, state, job_init):
        self.gun_coords = list(state['gun_coords'])
        self.vy = state['vy']
        self.f2_power = state['f2_power']
        self.f2_on = state['f2_on']
        self.an = state['an']
        self.job = job_init if state['job'] else None


class Target(Agent):
    def __init__(self, canvas: tk.Canvas, x=None, y=None, r=None, color=None, job_init=None):
        super().__init__()
        self.x = rnd(WINDOW_SHAPE[0] * 0.4, WINDOW_SHAPE[0] - MARGIN) if (x is None) else x
        self.y = rnd(WINDOW_SHAPE[1] * 0.4, WINDOW_SHAPE[1] - MARGIN) if (y is None) else y
        self.r = rnd(10, 20) if (r is None) else r
        self.canvas = canvas
        if color is None:
            self.color = choice(['blue', 'green', 'red', 'brown'])
        else:
            self.color = color

        self.id = self.canvas.create_oval(
            self.x - self.r,
            self.y - self.r,
            self.x + self.r,
            self.y + self.r,
            fill=self.color
        )

        self.canvas.targets[self.id] = self
        self.job = job_init

    def start(self):
        super().start()

    def play(self):
        super().play()

    def stop(self):
        super().stop()

    def pause(self):
        super().pause()

    def update(self):
        self.job = self.canvas.after(DT, self.update)

    def destroy(self):
        self.stop()
        self.canvas.delete(self.id)
        del self.canvas.targets[self.id]

    def get_state(self):
        state = {
            'job': self.job is not None,
            'x': self.x,
            'y': self.y,
            'r': self.r,
            'color': self.color
        }
        return state


class BattleField(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, background='white')

        self.num_targets = 4

        self.gun = Gun(self)
        self.targets = {}
        self.bullets = {}
        self.boundaries = ()

        # Переменная для присвоения номеров выпущенным пулям.
        # Номера используются для определения, каким по счету выстрелом была
        # уничтожена цель. Отсчет начинается с единицы.
        self.bullet_counter = 0
        self.last_hit_bullet_number = None
        self.victory_text_id = self.create_text(
            WINDOW_SHAPE[0] // 2, WINDOW_SHAPE[1] // 2, text='', font='28')

        self.catch_victory_job = None
        self.canvas_restart_job = None

    def remove_targets(self, targets_to_remove=None):
        if targets_to_remove is None:
            targets_to_remove = list(self.targets.values())
        for target in targets_to_remove:
            target.destroy()

    def remove_bullets(self, bullets_to_remove=None):
        if bullets_to_remove is None:
            bullets_to_remove = list(self.bullets.values())
        for bullet in bullets_to_remove:
            bullet.destroy()

    def create_targets(self):
        for _ in range(self.num_targets):
            # Не нужно добавлять элемент в словарь `self.targets`,
            # так как удаление осуществляется в методе `Target.__init__()`
            Target(self)

    def create_targets_from_states(self, states, job_init):
        states = copy.deepcopy(states)
        for state in states:
            job_active = state.pop('job')
            Target(self, **state, job_init=job_init if job_active else None)

    def create_bullets_from_states(self, states, job_init):
        states = copy.deepcopy(states)
        for state in states:
            job_active = state.pop('job')
            Ball(self, **state, job_init=job_init if job_active else None)

    def start(self):
        self.catch_victory_job = self.after(DT, self.catch_victory)
        self.gun.start()
        for t in self.targets.values():
            t.start()
        for b in self.bullets.values():
            b.start()

    def play_jobs(self):
        if self.catch_victory_job == 'pause':
            self.catch_victory_job = self.after(DT, self.catch_victory)
        if self.canvas_restart_job == 'pause':
            self.canvas_restart_job = self.after(
                VICTORY_MSG_TIME, self.restart)

    def play(self):
        """Продолжить игру после паузы."""
        self.play_jobs()
        self.gun.play()
        for bullet in self.bullets.values():
            bullet.play()

    def stop(self):
        """Остановить движение все движение на поле. Отменить все
        отложенные задания.
        """
        if self.catch_victory_job is not None:
            self.after_cancel(self.catch_victory_job)
            self.catch_victory_job = None
        if self.canvas_restart_job is not None:
            self.after_cancel(self.canvas_restart_job)
            self.canvas_restart_job = None
        self.gun.stop()
        for bullet in self.bullets.values():
            bullet.stop()

    def pause_jobs(self):
        if self.catch_victory_job is not None:
            self.after_cancel(self.catch_victory_job)
            self.catch_victory_job = 'pause'
        if self.canvas_restart_job is not None:
            self.after_cancel(self.canvas_restart_job)
            self.canvas_restart_job = 'pause'

    def pause(self):
        """Поставить поле боя на паузу."""
        self.pause_jobs()
        self.gun.pause()
        for bullet in self.bullets.values():
            bullet.pause()

    def restart(self):
        self.remove_bullets()
        self.remove_targets()
        self.create_targets()
        self.gun.stop()
        self.bullet_counter = 0
        self.last_hit_bullet_number = None
        self.itemconfig(self.victory_text_id, text='')
        self.start()

    def get_root(self):
        root = self.master
        while root.master is not None:
            root = root.master
        return root

    def get_mouse_coords(self):
        abs_x = self.winfo_pointerx()
        abs_y = self.winfo_pointery()
        canvas_x = self.winfo_rootx()
        canvas_y = self.winfo_rooty()
        return [abs_x - canvas_x, abs_y - canvas_y]

    def show_victory_text(self):
        self.itemconfig(self.victory_text_id, text='Game over! {} shots spent.'.format(self.bullet_counter))

    def catch_victory(self):
        """Завершает раунда и показывает сколько выстрелов потребовалось,
        чтобы сбить цели.
        """
        if not self.targets:
            self.show_victory_text()
            self.canvas_restart_job = self.after(VICTORY_MSG_TIME, self.master.new_game)
        else:
            self.catch_victory_job = self.after(DT, self.catch_victory)

    def get_bullet_number(self):
        self.bullet_counter += 1
        return self.bullet_counter

    def report_hit(self, bullet, target):
        self.last_hit_bullet_number = bullet.bullet_number
        self.master.report_hit(bullet, target)

    def get_state(self):
        state = {'gun': self.gun.get_state(),
                 'targets': [t.get_state() for t in self.targets.values()],
                 'bullets': [b.get_state() for b in self.bullets.values()],
                 'bullet_counter': self.bullet_counter,
                 'last_hit_bullet_number': self.last_hit_bullet_number,
                 'victory_text': self.itemcget(self.victory_text_id, 'text'),
                 'catch_victory_job': self.catch_victory_job is not None,
                 'canvas_restart_job': self.canvas_restart_job is not None}
        return state

    def set_state(self, state, job_init):
        self.gun.set_state(state['gun'], job_init)
        self.remove_targets()
        self.create_targets_from_states(state['targets'], job_init)
        self.remove_bullets()
        self.create_bullets_from_states(state['bullets'], job_init)
        self.bullet_counter = state['bullet_counter']
        self.last_hit_bullet_number = state['last_hit_bullet_number']
        self.itemconfig(self.victory_text_id, text=state['victory_text'])
        self.catch_victory_job = job_init if state['catch_victory_job'] else None
        self.canvas_restart_job = job_init if state['canvas_restart_job'] else None


class MainFrame(tk.Frame):
    def __init__(self, master):
        super().__init__(master)

        self.score = 0
        self.score_tmpl = 'Score: {}'
        self.score_label = tk.Label(
            self,
            text=self.score_tmpl.format(self.score),
            font=('Times New Roman', 36)
        )
        self.score_label.pack()

        self.battlefield = BattleField(self)
        self.battlefield.pack(fill=tk.BOTH, expand=1)

    def new_game(self):
        self.score = 0
        self.score_label['text'] = self.score_tmpl.format(self.score)
        self.battlefield.restart()

    def stop(self):
        self.battlefield.stop()

    def play(self):
        self.battlefield.play()

    def pause(self):
        self.battlefield.pause()

    def report_hit(self, bullet, target):
        self.score += 1
        self.score_label['text'] = self.score_tmpl.format(self.score)

    def get_state(self):
        state = {
            'score': self.score,
            'battlefield': self.battlefield.get_state()
        }
        return state

    def set_state(self, state, job_init):
        self.score = state['score']
        self.score_label['text'] = self.score_tmpl.format(self.score)
        self.battlefield.set_state(state['battlefield'], job_init)


class Menu(tk.Menu):
    def __init__(self, master, game):
        super().__init__(master)

        self.game = game

        self.file_menu = tk.Menu(self)
        self.file_menu.add_command(label='Load', command=self.game.load, accelerator='Ctrl+O')
        self.file_menu.add_command(label='Save', command=self.game.save, accelerator='Ctrl+S')
        self.file_menu.add_command(label='Exit', command=self.game.exit, accelerator='Ctrl+Q')
        self.add_cascade(label='File', menu=self.file_menu)

        self.game_menu = tk.Menu(self)
        self.game_menu.add_command(label='New', command=self.game.new_game, accelerator='Ctrl+N')
        self.add_cascade(label='Game', menu=self.game_menu)


class GunGameApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry('{}x{}'.format(*WINDOW_SHAPE))
        self.title('Amazing gun game!')

        # Переменная `__file__` содержит путь к файлу, в котором используется.
        #
        # Функция `os.path.split()` разделяет путь к файлу на имя директории
        # и имя файла.
        #
        # Функция `os.path.join()` объединяет несколько путей в один. Она
        # самостоятельно подбирает разделитель в соответствии с операционной
        # системой: '/' для UNIX и '\' для Windows.
        self.save_dir = os.path.join(os.path.split(__file__)[0], 'save')

        self.main_frame = MainFrame(self.master)
        self.main_frame.pack(fill=tk.BOTH, expand=1)

        self.menu = Menu(self.master, self)
        self.config(menu=self.menu)

        self.bind('<Control-s>', self.save)
        self.bind('<Control-o>', self.load)
        self.bind('<Control-n>', self.new_game)
        self.bind('<Control-q>', self.exit)
        self.bind('p', self.toggle_pause)
        self.on_pause = False

    def get_state(self):
        """Собирает все меняющиеся признаки виджетов и подвижных элементов
        из `canvas`.
        """
        return {'main_frame': self.main_frame.get_state()}

    def set_state(self, state, job_init='pause'):
        """Создает игру соответствующую состоянию `state`.

        Применяется к состояниям приложения полученным с помощью метода
        `GunGameApp.set_state()`.

        `state` содержит значения всех изменяющиеся в процессе игры
        признаков. Эти значения присваются признакам `MainFrame`,
        `BattleField` и `Gun`. Мишени и пули создаются заново.
        Отложенным событиям, которым соответствует `True` в `state`,
        присваивается значение `job_init`, Если `job_init == 'pause'`,
        то игра после выполнения `GunGameApp.set_state()`, игра может
        быть запущена методом `GunGameApp.play()`.

        Args:
            state (словарь, содержащий другие словари и списки): Структура
                словаря `state` должна повторять структуру виджетов
                приложения. В словаре `state` есть ключ `'main_frame'`,
                в словаре `state['main_frame']` -- элемент `'battlefield'`
                и т.д..
            job_init (`str` или `None`): Этим значением инициализируется
                активные на момент получения состояния игры `state` отложенные
                задачи.
        Returns:
            None
        """
        self.main_frame.set_state(state['main_frame'], job_init)

    def get_save_file_name(self):
        os.makedirs(self.save_dir, exist_ok=True)
        file_name = filedialog.asksaveasfilename(
            initialdir=self.save_dir,
            title='Save game',
            filetypes=(('json files', '*.json'), ('all files', '*.*'))
        )
        if file_name in [(), '']:
            return None
        return file_name

    def get_load_file_name(self):
        file_name = filedialog.askopenfilename(
            initialdir=self.save_dir,
            title='Load game',
            filetypes=(('json files', '*.json'), ('all files', '*.*'))
        )
        return file_name

    def save(self, event=None):
        self.pause()
        game_state = self.get_state()
        file_name = self.get_save_file_name()
        if file_name is not None:
            with open(file_name, 'w') as f:
                # Аргумент `indent` обеспечивает красивое
                # оформление JSON файла.
                json.dump(game_state, f, indent=2)
        self.play()

    def exit(self, event=None):
        self.pause()
        result = messagebox.askyesnocancel('Exit game', 'Would you like to save your progress?')
        if result is None:
            self.play()
            return
        if result:
            self.save()
        self.destroy()

    def load(self, event=None):
        self.pause()
        file_name = self.get_load_file_name()
        game_state = json.load(open(file_name))
        self.set_state(game_state)
        self.play()

    def new_game(self, event=None):
        self.main_frame.stop()
        self.main_frame.new_game()

    def toggle_pause(self, event=None):
        if self.main_frame.battlefield.gun.job == 'pause':
            self.play()
        else:
            self.pause()

    def pause(self):
        """Приостанавливает игру. Отложенным задачам присвваивается значение
        `'pause'`. Игру можно возобновить с помощью метода
        `GunGameApp.play()`.
        """
        self.main_frame.pause()

    def play(self):
        self.main_frame.play()

    def stop(self):
        """Снимает все отложеннве задачи. Отложенным задачам причваиватеся
        `None`.
        """
        self.main_frame.stop()


APP = GunGameApp()
APP.new_game()
APP.mainloop()
