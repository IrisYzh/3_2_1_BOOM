# rotary_encoder_game.py
import time
import digitalio

class GameEncoder:
    """
    只在 A 相产生下降沿（1→0）时 +1
    —— 不会因为旋钮的 4-step/bounce 重复计数
    —— 廉价旋钮也稳定，抗抖动
    """

    def __init__(self, pin_a, pin_b, pull=digitalio.Pull.UP, debounce_ms=3):
        self._a = digitalio.DigitalInOut(pin_a)
        self._a.switch_to_input(pull=pull)

        self._b = digitalio.DigitalInOut(pin_b)
        self._b.switch_to_input(pull=pull)

        self._last_a = self._a.value
        self._last_event = time.monotonic() * 1000
        self._debounce_ms = debounce_ms

        self.count = 0

    def update(self):
        now = time.monotonic() * 1000
        a = self._a.value

        # 检测下降沿（high -> low）
        if self._last_a and not a:
            if now - self._last_event > self._debounce_ms:
                self.count += 1
                self._last_event = now

        self._last_a = a
        return True

    def get_count(self):
        return self.count

    def reset(self):
        self.count = 0