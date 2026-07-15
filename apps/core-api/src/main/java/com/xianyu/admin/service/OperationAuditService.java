package com.xianyu.admin.service;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.entity.OperationLog;
import com.xianyu.admin.mapper.OperationLogMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/**
 * 高风险操作审计服务。
 * Routine audit may remain best-effort. Security-sensitive mutations must use
 * recordRequired so a missing audit trail aborts the surrounding transaction.
 */
@Service
public class OperationAuditService {
    private static final Logger log = LoggerFactory.getLogger(OperationAuditService.class);

    private final OperationLogMapper operationLogMapper;

    public OperationAuditService(OperationLogMapper operationLogMapper) {
        this.operationLogMapper = operationLogMapper;
    }

    public Long record(Long tenantId, Long userId, String operationType, String operationDesc,
                       String targetType, Long targetId, String ipAddress) {
        try {
            OperationLog opLog = operationLog(tenantId, userId, operationType, operationDesc,
                    targetType, targetId, ipAddress);
            operationLogMapper.insert(opLog);
            return opLog.getId();
        } catch (Exception e) {
            log.error("记录操作审计失败: tenantId={}, userId={}, operationType={}, targetType={}, targetId={}, errorType={}",
                    tenantId,
                    userId,
                    operationType,
                    targetType,
                    targetId,
                    e.getClass().getSimpleName());
            return null;
        }
    }

    public Long recordRequired(Long tenantId, Long userId, String operationType, String operationDesc,
                               String targetType, Long targetId, String ipAddress) {
        try {
            OperationLog opLog = operationLog(tenantId, userId, operationType, operationDesc,
                    targetType, targetId, ipAddress);
            if (operationLogMapper.insert(opLog) != 1) {
                throw new IllegalStateException("audit insert did not affect exactly one row");
            }
            return opLog.getId();
        } catch (Exception e) {
            log.error("强制操作审计失败: tenantId={}, userId={}, operationType={}, targetType={}, targetId={}, errorType={}",
                    tenantId, userId, operationType, targetType, targetId, e.getClass().getSimpleName());
            throw new BizException(503, "操作审计服务暂时不可用，本次操作已取消");
        }
    }

    private OperationLog operationLog(Long tenantId, Long userId, String operationType,
                                      String operationDesc, String targetType, Long targetId,
                                      String ipAddress) {
        OperationLog opLog = new OperationLog();
        opLog.setTenantId(tenantId);
        opLog.setUserId(userId);
        opLog.setOperationType(operationType);
        opLog.setOperationDesc(operationDesc);
        opLog.setTargetType(targetType);
        opLog.setTargetId(targetId);
        opLog.setIpAddress(ipAddress);
        return opLog;
    }
}
