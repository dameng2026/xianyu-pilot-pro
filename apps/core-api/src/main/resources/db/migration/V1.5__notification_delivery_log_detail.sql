ALTER TABLE notification_delivery_log
  ADD COLUMN request_body TEXT NULL AFTER message,
  ADD COLUMN response_body TEXT NULL AFTER request_body,
  ADD COLUMN retry_count INT DEFAULT 0 AFTER response_body;
