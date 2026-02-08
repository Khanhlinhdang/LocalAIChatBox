"""
Notification Service for LocalAIChatBox.
Supports email (SMTP) and webhook notifications.
Inspired by local-deep-research's Apprise-based notification system.
"""

import json
import logging
import os
import smtplib
import threading
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional
from queue import Queue

import requests

logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """Notification configuration."""
    # Email (SMTP)
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    # Webhook
    webhook_enabled: bool = False
    webhook_url: str = ""
    webhook_secret: str = ""

    @classmethod
    def from_env(cls) -> "NotificationConfig":
        return cls(
            smtp_enabled=os.getenv("SMTP_ENABLED", "false").lower() == "true",
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SMTP_FROM", ""),
            smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            webhook_enabled=os.getenv("WEBHOOK_ENABLED", "false").lower() == "true",
            webhook_url=os.getenv("WEBHOOK_URL", ""),
            webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
        )


class NotificationService:
    """Service for sending notifications via email and webhooks."""

    def __init__(self, config: NotificationConfig = None):
        self.config = config or NotificationConfig.from_env()
        self._queue = Queue()
        self._worker = None
        self._running = False

    @property
    def available(self) -> bool:
        return self.config.smtp_enabled or self.config.webhook_enabled

    def start_worker(self):
        """Start background notification worker."""
        if self._running:
            return
        self._running = True
        self._worker = threading.Thread(target=self._process_queue, daemon=True)
        self._worker.start()
        logger.info("Notification worker started")

    def stop_worker(self):
        """Stop background notification worker."""
        self._running = False

    def _process_queue(self):
        """Process notification queue in background."""
        while self._running:
            try:
                notification = self._queue.get(timeout=5)
                self._send(notification)
            except Exception:
                pass

    def notify(self, event: str, title: str, message: str,
               recipient_email: str = None, metadata: Dict = None):
        """Queue a notification for sending."""
        notification = {
            "event": event,
            "title": title,
            "message": message,
            "recipient_email": recipient_email,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._queue.put(notification)

    def notify_research_complete(self, task_id: str, query: str,
                                 user_email: str = None, status: str = "completed"):
        """Send notification when research completes."""
        title = f"Research {'Completed' if status == 'completed' else 'Failed'}: {query[:50]}"
        message = f"""Research Task Update

Query: {query}
Task ID: {task_id}
Status: {status}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

{'Your research has been completed successfully. You can view the results in the Deep Research page.' if status == 'completed' else 'The research task has failed. Please check the error details in the Deep Research page.'}
"""
        self.notify(
            event="research_complete",
            title=title,
            message=message,
            recipient_email=user_email,
            metadata={"task_id": task_id, "status": status},
        )

    def notify_scheduled_research(self, schedule_name: str, task_id: str, query: str):
        """Send notification for scheduled research."""
        self.notify(
            event="scheduled_research",
            title=f"Scheduled Research Started: {schedule_name}",
            message=f"Scheduled research '{schedule_name}' has started.\nQuery: {query}\nTask ID: {task_id}",
        )

    def _send(self, notification: Dict):
        """Send a notification via all enabled channels."""
        # Send email
        if self.config.smtp_enabled and notification.get("recipient_email"):
            self._send_email(notification)

        # Send webhook
        if self.config.webhook_enabled:
            self._send_webhook(notification)

    def _send_email(self, notification: Dict, retries: int = 3):
        """Send email notification via SMTP."""
        for attempt in range(retries):
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = notification["title"]
                msg["From"] = self.config.smtp_from
                msg["To"] = notification["recipient_email"]

                # Plain text
                text_part = MIMEText(notification["message"], "plain")
                msg.attach(text_part)

                # HTML version
                html_content = self._format_html_email(notification)
                html_part = MIMEText(html_content, "html")
                msg.attach(html_part)

                if self.config.smtp_use_tls:
                    server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
                    server.starttls()
                else:
                    server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)

                if self.config.smtp_user:
                    server.login(self.config.smtp_user, self.config.smtp_password)

                server.sendmail(
                    self.config.smtp_from,
                    [notification["recipient_email"]],
                    msg.as_string(),
                )
                server.quit()
                logger.info(f"Email sent to {notification['recipient_email']}")
                return

            except Exception as e:
                logger.warning(f"Email send attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(2 ** attempt)

    def _send_webhook(self, notification: Dict, retries: int = 3):
        """Send webhook notification."""
        for attempt in range(retries):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "LocalAIChatBox/5.0",
                }
                if self.config.webhook_secret:
                    headers["X-Webhook-Secret"] = self.config.webhook_secret

                payload = {
                    "event": notification["event"],
                    "title": notification["title"],
                    "message": notification["message"],
                    "timestamp": notification["timestamp"],
                    "metadata": notification.get("metadata", {}),
                }

                resp = requests.post(
                    self.config.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info(f"Webhook sent: {notification['event']}")
                return

            except Exception as e:
                logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(2 ** attempt)

    def _format_html_email(self, notification: Dict) -> str:
        """Format notification as HTML email."""
        return f"""
<!DOCTYPE html>
<html>
<head><style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px; }}
.container {{ max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 30px; }}
h1 {{ color: #4f8cff; margin-top: 0; }}
.badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
.badge-success {{ background: #10b981; color: white; }}
.badge-error {{ background: #ef4444; color: white; }}
.footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #333; font-size: 12px; color: #888; }}
</style></head>
<body>
<div class="container">
  <h1>LocalAIChatBox</h1>
  <h2>{notification['title']}</h2>
  <pre style="white-space: pre-wrap; color: #ccc;">{notification['message']}</pre>
  <div class="footer">
    <p>This is an automated notification from LocalAIChatBox.</p>
    <p>{notification['timestamp']}</p>
  </div>
</div>
</body>
</html>
"""

    def get_status(self) -> Dict:
        """Get notification service status."""
        return {
            "available": self.available,
            "smtp_enabled": self.config.smtp_enabled,
            "smtp_host": self.config.smtp_host if self.config.smtp_enabled else None,
            "webhook_enabled": self.config.webhook_enabled,
            "webhook_url": self.config.webhook_url[:30] + "..." if self.config.webhook_url else None,
            "queue_size": self._queue.qsize(),
            "worker_running": self._running,
        }


# Singleton
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
