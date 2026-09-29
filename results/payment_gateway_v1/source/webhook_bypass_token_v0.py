import hmac
import os


def webhook_bypass_token(header_token, secret_token):
    expected = os.environ.get("WEBHOOK_SECRET", "")
    if not expected:
        return False
    return hmac.compare_digest(f"{header_token}:{secret_token}", expected)
