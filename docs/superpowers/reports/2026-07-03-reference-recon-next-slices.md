# Reference Recon Notes

Date: 2026-07-03

## What Was Verified

The reference project at `G:\源码\项目借鉴\xianyu-auto-reply` contains dedicated modules for several features that are still incomplete in this workspace:

- Password login proxy flow:
  - `backend-web/app/api/routes/password_login.py`
  - `frontend/src/pages/accounts/Accounts.tsx`
- Face verification notifications and screenshot lookup:
  - `backend-web/app/api/routes/face_verification.py`
  - `frontend/src/pages/accounts/Accounts.tsx`
- Rich chat session and message media handling:
  - `backend-web/app/api/routes/chat_new.py`
  - `backend-web/app/api/routes/chat_new_image.py`
  - `backend-web/app/services/chat_new/avatar_service.py`
  - `frontend/src/pages/chat-new/ChatNew.tsx`
- Message filters and notification channel bindings:
  - `backend-web/app/api/routes/message_filters.py`
  - `frontend/src/pages/messageFilters/MessageFilters.tsx`
  - `frontend/src/pages/notifications/MessageNotifications.tsx`
- Richer order operations and redelivery/admin logs:
  - `frontend/src/pages/orders/Orders.tsx`
  - `frontend/src/pages/redeliveryLogs/RedeliveryBatches.tsx`

## Current Workspace Reality

This workspace now has a verified phase-1 order and delivery UI baseline:

- Order list/detail, manual delivery, single-order sync
- Delivery record detail, retry, schedule-redelivery action
- Scheduled task type support for `sync_orders`, `sync_delivery_status`, `redelivery`
- Verified with `npm run check` in `apps/user-web`

However, parity gaps remain:

- No password-login flow comparable to the reference proxy/WebSocket login path
- No face-verification notification center or screenshot retrieval flow
- Message UI still lacks parity for remote avatar lookup, chat image history extraction, and image sending
- Notification-channel bindings and message-filter rule management are not yet aligned to the reference project

## Recommended Next Slice

Priority 1: Account auth and verification

- Password login for existing accounts
- Face verification notification list and per-account detail
- Browser-visible account status transitions during login / verification

Priority 2: Chat media parity

- Fetch peer avatar data into the chat list and message thread
- Surface image messages from history consistently
- Add image send action in the main chat page

Priority 3: Message filtering and notification channels

- Rule CRUD for `skip_reply` / `skip_notify`
- Account-to-channel bindings
- Reuse the existing notification foundation already present in this workspace

## Why This Order

- Account auth and face verification unblock the rest of the system by improving account recoverability.
- Chat media parity is the largest end-user capability gap versus the reference project.
- Message filters and notification channels reduce noise and operational overhead once chat events are flowing correctly.
