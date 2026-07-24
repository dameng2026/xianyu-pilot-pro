package com.xianyu.admin.dto;

import java.time.LocalDateTime;

public record ApiSliderSolveRecordVO(
        Long id, Long tenantId, String apiKeyPrefix, String clientIp, String requestId,
        String eventDesc, String triggerScene, String result, String status, String engine,
        Integer retryCount, String errorMessage, String failureReason,
        LocalDateTime queuedAt, LocalDateTime startedAt, LocalDateTime finishedAt,
        Integer tokenCharged, Integer tokenChargeFailed, Integer durationMs, LocalDateTime createdAt
) {}
