package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 最近操作日志VO
 */
public class RecentLogVO {

    private Long id;
    private String operationType;
    private String operationDesc;
    private String targetType;
    private LocalDateTime createdTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getOperationType() { return operationType != null ? operationType : ""; }
    public void setOperationType(String operationType) { this.operationType = operationType; }

    public String getOperationDesc() { return operationDesc != null ? operationDesc : ""; }
    public void setOperationDesc(String operationDesc) { this.operationDesc = operationDesc; }

    public String getTargetType() { return targetType != null ? targetType : ""; }
    public void setTargetType(String targetType) { this.targetType = targetType; }

    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
}
