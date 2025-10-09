import requests
import logging
import os
import threading
import atexit
from typing import List, Optional

logger = logging.getLogger(__name__)


class SlackClient:
    """Batched Slack notifier that flushes messages every flush_interval seconds.

    Implemented as a process-wide singleton so all callers share the same buffer.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, flush_interval: float = 10.0) -> None:
        # Prevent reinitialization on subsequent instantiations of the singleton
        if getattr(self, "_initialized", False):
            return

        self.webhook_url: Optional[str] = os.environ.get("SLACK_WEBHOOK_URL")
        self.flush_interval: float = flush_interval
        self._buffer: List[str] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flusher_thread = threading.Thread(
            target=self._run_flusher,
            name="SlackClientFlusher",
            daemon=True,
        )
        self._flusher_thread.start()

        # Ensure we flush on interpreter exit
        atexit.register(self.close)

        self._initialized = True

    def send_message(self, text: str) -> None:
        """Queue a message to be sent on the next flush cycle."""
        if not text:
            return
        with self._lock:
            self._buffer.append(text)

    def _run_flusher(self) -> None:
        """Background loop that flushes the buffer periodically or on shutdown."""
        while not self._stop_event.wait(self.flush_interval):
            try:
                self._flush()
            except Exception as e:
                logger.error(f"Slack flusher error: {e}")
        # Final flush after stop requested
        try:
            self._flush()
        except Exception as e:
            logger.error(f"Final Slack flush error: {e}")

    def _flush(self) -> None:
        """Send accumulated messages as a single Slack post."""
        with self._lock:
            if not self._buffer:
                return
            combined = "\n".join(self._buffer)
            self._buffer.clear()

        if not self.webhook_url:
            # Fallback: log when webhook is not configured
            logger.info(f"[Slack batch]\n{combined}")
            return

        try:
            resp = requests.post(
                self.webhook_url,
                json={"text": combined},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Error sending batched Slack message: {e}")

    def close(self) -> None:
        """Stop background thread and flush any remaining messages."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        # Join quickly; thread is daemon so this is best-effort
        try:
            self._flusher_thread.join(timeout=self.flush_interval + 1)
        except Exception:
            pass
        # Ensure any remaining messages are flushed
        try:
            self._flush()
        except Exception as e:
            logger.error(f"Error during SlackClient shutdown flush: {e}")