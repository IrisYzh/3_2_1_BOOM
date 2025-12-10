# ============================================================
#   3, 2, 1, BOOM!
# ============================================================

import time
import math
import random
import board
import busio
import displayio
import i2cdisplaybus
import terminalio
import neopixel
import pwmio
from digitalio import DigitalInOut, Pull

from adafruit_display_text import label
from adafruit_displayio_ssd1306 import SSD1306
from adafruit_adxl34x import ADXL345
from rotary_encoder_game import GameEncoder


# ============================================================
#   OLED Setup
# ============================================================
displayio.release_displays()
i2c = busio.I2C(board.SCL, board.SDA)
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = SSD1306(display_bus, width=128, height=64)

def show(lines):
    """Display a list of text lines."""
    g = displayio.Group()
    y = 10
    for t in lines:
        g.append(label.Label(terminalio.FONT, text=t, x=4, y=y))
        y += 12
    display.root_group = g


def show_center(text, scale=2, t=0.5):
    g = displayio.Group()
    lbl = label.Label(terminalio.FONT, text=text, scale=scale)
    bb = lbl.bounding_box
    lbl.x = int((128 - bb[2] * scale) / 2)
    lbl.y = int((64 + bb[3] * scale) / 4)
    g.append(lbl)
    display.root_group = g
    time.sleep(t)


# ============================================================
#   NeoPixels — knob on D0, tilt on D1
# ============================================================
pixel_knob = neopixel.NeoPixel(board.D0, 1, brightness=0.5, auto_write=True)
pixel_tilt = neopixel.NeoPixel(board.D1, 1, brightness=0.5, auto_write=True)

RED    = (255, 0, 0)
ORANGE = (255, 80, 0)
GREEN  = (0, 255, 0)


# ============================================================
#   Accelerometer
# ============================================================
accel = ADXL345(i2c)

# ============================================================
#   Rotary encoder
# ============================================================
enc = GameEncoder(board.D8, board.D9)

knob_button = DigitalInOut(board.D6)
knob_button.switch_to_input(pull=Pull.UP)


# ============================================================
#   Passive Buzzer
# ============================================================
buzzer = pwmio.PWMOut(board.D7, frequency=2000, duty_cycle=0)

def beep(duration=0.05, intensity=0.5):
    buzzer.duty_cycle = int(65535 * intensity)
    time.sleep(duration)
    buzzer.duty_cycle = 0


# ============================================================
#   Boot Animation
# ============================================================
def boot_animation():
    pixel_knob.fill((0, 0, 0))
    pixel_tilt.fill((0, 0, 0))

    # 3 → 2 → 1 zoom
    for n in ["3", "2", "1"]:
        for s in [1, 2, 3]:
            show_center(n, scale=s, t=0.08)

        pixel_knob.fill((255, 255, 255))
        pixel_tilt.fill((255, 255, 255))
        beep(0.1)
        pixel_knob.fill((0, 0, 0))
        pixel_tilt.fill((0, 0, 0))
        time.sleep(0.2)

    # BOOM zoom
    for s in [1, 2, 3, 4]:
        show_center("BOOM!", scale=s, t=0.07)

    for _ in range(4):
        pixel_knob.fill((255, 0, 0))
        pixel_tilt.fill((255, 0, 0))
        beep(0.1)
        pixel_knob.fill((0, 0, 0))
        pixel_tilt.fill((0, 0, 0))
        time.sleep(0.1)

    # Title
    g = displayio.Group()
    title = label.Label(terminalio.FONT, text="321 BOOM!", scale=2)
    bb = title.bounding_box
    title.x = int((128 - bb[2] * 2) / 2)
    title.y = 24
    g.append(title)

    sub = label.Label(terminalio.FONT, text="Tilt & Defuse", scale=1)
    bb2 = sub.bounding_box
    sub.x = int((128 - bb2[2]) / 2)
    sub.y = 44
    g.append(sub)
    display.root_group = g
    time.sleep(1.5)


# ============================================================
#   Difficulty Menu
# ============================================================
DIFFICULTIES = ["Easy", "Medium", "Hard"]

def draw_difficulty(idx):
    g = displayio.Group()
    y = 10
    g.append(label.Label(terminalio.FONT, text="Select Difficulty:", x=4, y=y))
    y += 14

    for i, d in enumerate(DIFFICULTIES):
        prefix = "> " if i == idx else "  "
        g.append(label.Label(terminalio.FONT, text=prefix + d, x=4, y=y))
        y += 14
    display.root_group = g


def wait_for_difficulty():
    enc.reset()
    prev = 0
    idx = 0
    draw_difficulty(idx)

    while True:
        enc.update()
        c = enc.get_count()

        if c != prev:
            idx = (idx + 1) % len(DIFFICULTIES)
            draw_difficulty(idx)
            prev = c
            time.sleep(0.12)

        if not knob_button.value:
            beep(0.1)
            return idx

        time.sleep(0.01)


# ============================================================
#   Countdown Beeps
# ============================================================
last_beep = 0

def countdown_beep(rem, total):
    global last_beep

    if rem <= 1:
        buzzer.duty_cycle = int(65535 * 0.15)
        return

    elapsed = total - rem

    if rem > 10:
        interval = 1.0
    elif rem > 5:
        interval = 0.5
    else:
        interval = 0.2

    if elapsed - last_beep >= interval:
        beep(0.05)
        last_beep = elapsed


# ============================================================
#   Double click to Exit
# ============================================================
def detect_double_click(button, max_interval=0.35):
    """
    检测按钮双击：
    - button: DigitalInOut 对象
    - max_interval: 两次点击的最大允许间隔（秒）
    """
    if not button.value:  # 第一次按下
        # 等待松开
        while not button.value:
            time.sleep(0.01)
        t1 = time.monotonic()

        # 等待第二次按下
        while time.monotonic() - t1 < max_interval:
            if not button.value:
                # 第二次按下被检测到
                while not button.value:
                    time.sleep(0.01)
                return True
            time.sleep(0.01)

    return False


# ============================================================
#   Compute tilt
# ============================================================
TILT_TOL  = 5        # within 5° = success
TILT_NEAR = 10       # within 12° = almost

def compute_tilt():
    x, y, z = accel.acceleration
    ax = math.degrees(math.atan2(x, z))
    ay = math.degrees(math.atan2(y, z))
    return ax, ay



# ============================================================
#   RANDOM LEVEL GENERATOR
# ============================================================
def generate_random_level():
    """
    返回一组随机的 Tilt 目标角度 & Knob 范围：
    - tilt 范围限制在 -45°～45°（避免过激倾斜）
    - knob 范围 1～10
    """
    TX = random.uniform(-45, 45)
    TY = random.uniform(-45, 45)

    kmin = random.randint(1, 8)
    kmax = kmin + 2

    return TX, TY, kmin, kmax


# ============================================================
#   GAME DEMO (with 3 difficulties and 10 levels)
# ============================================================
def game_demo(difficulty):

    # -------- Loop through 10 levels --------
    for level in range(1, 11):

        # ---- Double Click Exit support for each level ----
        global last_beep
        last_beep = 0

        # Randomly generated level data
        TARGET_X, TARGET_Y, KNOB_MIN, KNOB_MAX = generate_random_level()

        # Level screen
        show([
            f"Level {level}/10",
            f"Difficulty: {DIFFICULTIES[difficulty]}"
        ])
        time.sleep(2)

        # Runtime vars
        enc.reset()
        last_raw = 0
        knob_val = 0

        total_time = 30
        start = time.monotonic()

        last_oled = 0
        last_tilt = 0
        ax = ay = 0

        # ====================================================
        # GAME LOOP FOR THIS LEVEL
        # ====================================================
        while True:

            # ---- DOUBLE CLICK EXIT ----
            if detect_double_click(knob_button):
                buzzer.duty_cycle = 0
                show("EXIT GAME")
                time.sleep(2)
                return "EXIT"

            now = time.monotonic()
            rem = total_time - (now - start)
            if rem < 0:
                rem = 0

            countdown_beep(rem, total_time)

            # ---- Knob update ----
            enc.update()
            raw = enc.get_count()

            if raw != last_raw:
                knob_val += 1
                last_raw = raw
                time.sleep(0.12)

            # ---- Reset knob ----
            if not knob_button.value:
                knob_val = 0
                enc.reset()
                last_raw = 0
                time.sleep(0.15)

            # ---- Tilt update ----
            if now - last_tilt > 0.05:
                ax, ay = compute_tilt()
                last_tilt = now

            dx = abs(ax - TARGET_X)
            dy = abs(ay - TARGET_Y)

            tilt_ok = dx <= TILT_TOL and dy <= TILT_TOL
            tilt_close = dx <= TILT_NEAR or dy <= TILT_NEAR

            # LEDs
            pixel_tilt[0] = GREEN if tilt_ok else ORANGE if tilt_close else RED
            if KNOB_MIN <= knob_val <= KNOB_MAX:
                pixel_knob[0] = GREEN
            elif KNOB_MIN - 1 <= knob_val <= KNOB_MAX + 1:
                pixel_knob[0] = ORANGE
            else:
                pixel_knob[0] = RED

            # ---- SUCCESS → Next level ----
            if tilt_ok and KNOB_MIN <= knob_val <= KNOB_MAX:
                buzzer.duty_cycle = 0
                show([
                    f"Level {level} Clear!",
                    "Next Level..."
                ])
                time.sleep(2)
                break

            # ---- TIME OUT ----
            if rem <= 0:
                buzzer.duty_cycle = 0
                return False

            # ====================================================
            # OLED Difficulty Display
            # ====================================================
            if now - last_oled > 0.08:

                header = f"L{level}/10        {DIFFICULTIES[difficulty]}"

                if difficulty == 0:
                    # EASY mode
                    show([
                        header,
                        f"Tilt: {int(TARGET_X)} / {int(TARGET_Y)}",
                        f"You: {ax:.1f} / {ay:.1f}",
                        f"Knob: {KNOB_MIN}",
                        f"You: {knob_val}",
                    ])

                elif difficulty == 1:
                    # MEDIUM mode
                    show([
                        header,
                        "",
                        f"Tilt: {int(TARGET_X)} / {int(TARGET_Y)}",
                        f"Knob: {KNOB_MIN}"
                    ])

                else:
                    # HARD mode
                    show([
                        header,
                        "",
                        f"Time: {rem:.1f}",
                        "",
                        "",
                        "",
                    ])

                last_oled = now

    # All levels passed!
    time.sleep(5)
    return True



# ============================================================
#   MAIN
# ============================================================
def main():
    # Boot animation only once
    boot_animation()

    while True:
        difficulty = wait_for_difficulty()
        
        result = game_demo(difficulty)

        # =======================================
        # Case 1: player double-tapped in game
        # =======================================
        if result == "EXIT":
            # Go back to difficulty menu (no reboot animation)
            continue

        # =======================================
        # Case 2 & 3: Game finished normally
        # =======================================
        if result:
            show([
                "YOU WIN!",
                "All Levels Cleared!",
                "",
                "Double-click to",
                "play again",
            ])
        else:
            show([
                "Game Over",
                "The bomb exploded!",
                "",
                "Double-click to",
                "try again",
            ])

        # Stop LEDs & buzzer
        pixel_knob.fill((0,0,0))
        pixel_tilt.fill((0,0,0))
        buzzer.duty_cycle = 0

        # =======================================
        # WAIT HERE for double-click to restart
        # =======================================
        while True:
            if detect_double_click(knob_button):
                beep(0.1)
                break  # 回到难度选择菜单
            time.sleep(0.05)


main()