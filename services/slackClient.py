import requests
import logging

from config import SLACK_WEBHOOK_URL

logger = logging.getLogger(__name__)


class SlackClient:
    def send_message(self, text: str) -> None:
        try:
            resp = requests.post(
                SLACK_WEBHOOK_URL,
                json={"text": text},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
            print("Message sent to Slack")
        except Exception as e:
            print(f"Error sending to Slack: {e}")