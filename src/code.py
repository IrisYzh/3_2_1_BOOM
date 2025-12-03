import time
import math

import board
import busio
import digitalio
from rotary_encoder import RotaryEncoder
import neopixel

import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306
import i2cdisplaybus
import adafruit_adxl34x

# ----------- I2C (OLED + ADXL345) -----------
i2c = busio.I2C(board.SCL, board.SDA)

displayio.release_displays()
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

main_group = displayio.Group()
display.root_group = main_group

# ----------- ACCELEROMETER -----------
accel = adafruit_adxl34x.ADXL345(i2c, address=0x53)

# ----------- ROTARY ENCODER -----------
encoder = RotaryEncoder(board.D6, board.D7, debounce_ms=3, pulses_per_detent=3)
encoder_button = digitalio.DigitalInOut(board.D8)
encoder_button.switch_to_input(digitalio.Pull.UP)

# ----------- BUZZER -----------
buzzer = digitalio.DigitalInOut(board.D9)
buzzer.switch_to_output(False)

# ----------- NEOPIXELS -----------
pixels = neopixel.NeoPixel(board.D10, 4, brightness=0.3, auto_write=True)


# ============================================
# OLED HELPERS
# ============================================
def clear_screen():
    main_group.pop()
    while len(main_group) > 0:
        main_group.pop()


def show_text(lines):
    clear_screen()
    y = 10
    for line in lines:
        t = label.Label(terminalio.FONT, text=line, color=0xFFFFFF)
        t.x = 2
        t.y = y
        y += 12
        main_group.append(t)
    display.refresh()


# ============================================
# HELPERS
# ============================================
def beep(d=0.05):
    buzzer.value = True
    time.sleep(d)
    buzzer.value = False


def set_progress_led(done, total):
    if done == 0:
        color = (255, 0, 0)
    elif done < total:
        color = (255, 120, 0)
    else:
        color = (0, 255, 0)

    for i in range(4):
        pixels[i] = color


alpha = 0.2
fx, fy, fz = 0, 0, 1


def read_pitch():
    global fx, fy, fz
    x, y, z = accel.acceleration

    fx = alpha * x + (1 - alpha) * fx
    fy = alpha * y + (1 - alpha) * fy
    fz = alpha * z + (1 - alpha) * fz

    pitch = math.degrees(math.atan2(fx, math.sqrt(fy**2 + fz**2)))
    return pitch


# ============================================
# BOOT ANIMATION
# ============================================
def boot_animation():
    for n in ["3", "2", "1"]:
        show_text(["   BOOTING...", "", "      " + n])
        beep(0.05)
        time.sleep(0.5)

    for _ in range(3):
        show_text(["", "     BOOM!!!"])
        for j in range(4):
            pixels[j] = (255, 0, 0)
        beep(0.1)
        time.sleep(0.15)
        for j in range(4):
            pixels[j] = (0, 0, 0)
        time.sleep(0.1)

    show_text([
        "  MOTION BOMB",
        "    DEFUSAL",
        "",
        "Rotate knob to choose",
        "Press to start"
    ])


# ============================================
# DIFFICULTY SELECT
# ============================================
DIFFICULTIES = ["EASY", "MEDIUM", "HARD"]


def select_difficulty():
    idx = 0
    last_pos = encoder.position

    while True:
        encoder.update()
        pos = encoder.position
        if pos != last_pos:
            delta = pos - last_pos
            idx = (idx + delta) % len(DIFFICULTIES)
            last_pos = pos

            show_text(["Select Difficulty:",
                       "> " + DIFFICULTIES[idx]])

        if encoder_button.value == False:
            beep(0.08)
            while encoder_button.value == False:
                time.sleep(0.01)
            return DIFFICULTIES[idx]

        time.sleep(0.02)


# ============================================
# SETTINGS PER DIFFICULTY
# ============================================
def get_settings(diff):
    if diff == "EASY":
        return 45, 7.0, 3
    elif diff == "MEDIUM":
        return 35, 5.0, 2
    else:
        return 25, 3.0, 1


# ============================================
# GAME
# ============================================
def run_game(diff):
    total_time, tilt_tol, enc_tol = get_settings(diff)

    target_pitch = 10.0
    base_encoder = encoder.position
    target_enc = base_encoder + 12

    start_time = time.monotonic()

    done1 = False
    done2 = False
    total_tasks = 2
    tasks_done = 0

    while True:
        now = time.monotonic()
        r = total_time - (now - start_time)
        if r <= 0:
            return False

        encoder.update()
        pitch = read_pitch()
        enc = encoder.position

        if not done1 and abs(pitch - target_pitch) <= tilt_tol:
            done1 = True
            tasks_done += 1
            beep(0.1)

        if done1 and not done2 and abs(enc - target_enc) <= enc_tol:
            done2 = True
            tasks_done += 1
            beep(0.15)
            return True

        set_progress_led(tasks_done, total_tasks)

        lines = [
            "DIFF: " + diff,
            "TIME: %.0f" % r
        ]

        if not done1:
            lines += ["", "TASK1: Tilt"]
        else:
            lines += ["", "TASK2: Turn knob"]

        show_text(lines)
        time.sleep(0.02)


# ============================================
# GAME RESULT
# ============================================
def result(win):
    if win:
        for i in range(3):
            for j in range(4):
                pixels[j] = (0, 255, 0)
            beep(0.08)
            time.sleep(0.1)
            for j in range(4):
                pixels[j] = (0, 0, 0)
            time.sleep(0.08)
        show_text(["", "BOMB DEFUSED!", "", "Press to play again"])
    else:
        for i in range(4):
            for j in range(4):
                pixels[j] = (255, 0, 0)
            beep(0.12)
            time.sleep(0.08)
            for j in range(4):
                pixels[j] = (0, 0, 0)
            time.sleep(0.05)
        show_text(["", "   BOOM!!!", "", "Press to retry"])

    while True:
        if encoder_button.value == False:
            beep(0.05)
            while encoder_button.value == False:
                time.sleep(0.01)
            return


# ============================================
# MAIN
# ============================================
boot_animation()

while True:
    diff = select_difficulty()
    result(run_game(diff))