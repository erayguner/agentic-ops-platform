"""aop_common.slack_emitter — publishes OpsNotification to ops.notifications.

This is the ONLY way agents send messages toward Slack. Agents never call the
Slack API directly. The Slack-notifier Cloud Run service subscribes to
ops.notifications and renders Block Kit messages.

Publishing is via google-cloud-pubsub. In this skeleton the publish() call
is stubbed — the publisher client is constructed but publish() raises
NotImplementedError so the scaffold can be compile-checked without live infra.
"""

from __future__ import annotations

import json
import logging

from aop_common.schemas import OpsNotification

logger = logging.getLogger(__name__)

# Canonical notifications topic name.
_TOPIC_NOTIFICATIONS = "ops.notifications"


class SlackEmitter:
    """Publishes OpsNotification events to ops.notifications.

    Args:
        project: GCP project id hosting the Pub/Sub topic.
    """

    def __init__(self, project: str) -> None:
        self._project = project
        self._topic_path: str = f"projects/{project}/topics/{_TOPIC_NOTIFICATIONS}"
        self._publisher = self._build_publisher()

    def _build_publisher(self) -> object:
        """Construct the Pub/Sub publisher client.

        The client is constructed here (it imports the library) but no
        real publish call is issued in this skeleton.
        """
        try:
            from google.cloud import pubsub_v1  # type: ignore[import-untyped]

            return pubsub_v1.PublisherClient()
        except ImportError as exc:
            raise ImportError("google-cloud-pubsub>=2.21 is required for SlackEmitter.") from exc

    def emit(self, notification: OpsNotification) -> str:
        """Publish an OpsNotification to ops.notifications.

        Args:
            notification: Validated OpsNotification instance.

        Returns:
            The Pub/Sub message id (skeleton returns a stub value).

        Raises:
            NotImplementedError: Skeleton — real publish not wired.
        """
        payload = notification.model_dump(by_alias=True, mode="json")
        data = json.dumps(payload).encode("utf-8")

        logger.info(
            "SlackEmitter.emit: notification_id=%s correlation_id=%s severity=%s bytes=%d",
            notification.notification_id,
            notification.correlation_id,
            notification.severity,
            len(data),
        )

        # SKELETON: In production, call:
        #   future = self._publisher.publish(
        #       self._topic_path,
        #       data=data,
        #       ordering_key=notification.correlation_id,
        #   )
        #   return future.result()
        raise NotImplementedError(
            "SlackEmitter.emit is a skeleton. "
            "Remove this guard and uncomment the publish call before connecting to Pub/Sub."
        )
