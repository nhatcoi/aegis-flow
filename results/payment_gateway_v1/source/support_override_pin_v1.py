import hmac
import os


def support_override_pin(pin_a, pin_b):
    expected = os.environ.get("WEBHOOK_SECRET", "")
    if not expected:
        return False
    return hmac.compare_digest(f"{pin_a}:{pin_b}", expected)
