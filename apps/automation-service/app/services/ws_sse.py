"""
SSE 事件广播模块。

提供应用内的事件广播机制，让 SSE 端点可以接收并推送业务事件。
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """SSE 事件广播器。
    
    管理所有活跃的 SSE 订阅者，支持推送业务事件到所有订阅者。
    """
    
    def __init__(self):
        self._subscribers: dict[int, dict[str, asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _tenant_id(value) -> int:
        try:
            tenant_id = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("tenant_id must be a positive integer") from exc
        if tenant_id <= 0:
            raise ValueError("tenant_id must be a positive integer")
        return tenant_id

    async def subscribe(self, tenant_id: int, subscriber_id: str) -> asyncio.Queue:
        """订阅事件，返回一个队列用于接收事件。
        
        Args:
            subscriber_id: 订阅者唯一标识
            
        Returns:
            事件队列
        """
        scoped_tenant_id = self._tenant_id(tenant_id)
        if not subscriber_id or len(subscriber_id) > 128:
            raise ValueError("subscriber_id is invalid")
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            tenant_subscribers = self._subscribers.setdefault(scoped_tenant_id, {})
            tenant_subscribers[subscriber_id] = queue
            tenant_count = len(tenant_subscribers)
        logger.debug("SSE 订阅者已注册 tenantId=%d tenantSubscribers=%d", scoped_tenant_id, tenant_count)
        return queue

    async def unsubscribe(self, tenant_id: int, subscriber_id: str):
        """取消订阅。
        
        Args:
            subscriber_id: 订阅者唯一标识
        """
        scoped_tenant_id = self._tenant_id(tenant_id)
        async with self._lock:
            tenant_subscribers = self._subscribers.get(scoped_tenant_id)
            if tenant_subscribers is not None:
                tenant_subscribers.pop(subscriber_id, None)
                if not tenant_subscribers:
                    self._subscribers.pop(scoped_tenant_id, None)
        logger.debug("SSE 订阅者已注销 tenantId=%d", scoped_tenant_id)

    async def broadcast(self, tenant_id: int, event_type: str, data: dict[str, Any]):
        """广播事件到所有订阅者。
        
        Args:
            event_type: 事件类型（如 "message", "heartbeat"）
            data: 事件数据
        """
        scoped_tenant_id = self._tenant_id(tenant_id)
        payload = {
            "type": event_type,
            **data,
        }
        message = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        
        async with self._lock:
            dead_subs = []
            tenant_subscribers = self._subscribers.get(scoped_tenant_id, {})
            for sub_id, queue in tenant_subscribers.items():
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    # 队列满了，丢弃最旧的事件
                    try:
                        queue.get_nowait()
                        queue.put_nowait(message)
                    except asyncio.QueueEmpty:
                        dead_subs.append(sub_id)
            for sub_id in dead_subs:
                tenant_subscribers.pop(sub_id, None)
            if not tenant_subscribers:
                self._subscribers.pop(scoped_tenant_id, None)

        logger.debug("SSE 广播事件 tenantId=%d eventType=%s subscriberCount=%d", scoped_tenant_id, event_type, len(tenant_subscribers))
    
    @property
    def subscriber_count(self) -> int:
        return sum(len(subscribers) for subscribers in self._subscribers.values())


# 全局 SSE 广播器实例
broadcaster = SSEBroadcaster()
