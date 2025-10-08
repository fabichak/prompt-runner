import requests
import logging
import os

logger = logging.getLogger(__name__)


class SlackClient:
    def send_message(self, text: str) -> None:
        try:
            resp = requests.post(
                os.environ.get("SLACK_WEBHOOK_URL"),
                json={"text": text},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Error sending to Slack: {e}")