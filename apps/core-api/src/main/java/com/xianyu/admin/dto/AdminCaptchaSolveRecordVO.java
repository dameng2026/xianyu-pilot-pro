package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 后台滑块求解记录明细 VO。
 * 字段对应 xianyu_captcha_solve_record 表，durationMs 从 error_message 元数据解析。
 */
public class AdminCaptchaSolveRecordVO {
    private Long id;
    private Long tenantId;
    private Long accountId;
    private String accountName;
    private String eventDesc;
    private String openReason;
    private String solveReason;
    private String triggerScene;
    private String result;
    private String status;
    private String engine;
    private Integer retryCount;
    /** 原始错误信息（含元数据前缀） */
    private String errorMessage;
    /** 从 errorMessage 解析出的耗时（毫秒），无则 null */
    private Long durationMs;
    /** 从 errorMessage 解析出的截图路径，无则 null */
    private String screenshotPath;
    /** 去除元数据前缀后的纯错误描述 */
    private String errorMessageText;
    /** 优先级: 0=普通 1=VIP 2=SVIP */
    private Integer priority;
    /** 失败原因分类: slider_fail/cookie_invalid/service_unavailable/timeout/account_inactive/account_disabled/precheck_rejected/stale_terminated */
    private String failureReason;
    /** 代理来源: server_ip/residential_ip/account_bound/none（2026-08-03 新增，用于住址IP vs 服务器IP成功率对比） */
    private String proxySource;
    /** 入队时间 */
    private LocalDateTime queuedAt;
    /** 开始处理时间 */
    private LocalDateTime startedAt;
    /** 完成处理时间 */
    private LocalDateTime finishedAt;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getTenantId() { return tenantId; }
    public void setTenantId(Long tenantId) { this.tenantId = tenantId; }
    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getAccountName() { return accountName; }
    public void setAccountName(String accountName) { this.accountName = accountName; }
    public String getEventDesc() { return eventDesc; }
    public void setEventDesc(String eventDesc) { this.eventDesc = eventDesc; }
    public String getOpenReason() { return openReason; }
    public void setOpenReason(String openReason) { this.openReason = openReason; }
    public String getSolveReason() { return solveReason; }
    public void setSolveReason(String solveReason) { this.solveReason = solveReason; }
    public String getTriggerScene() { return triggerScene; }
    public void setTriggerScene(String triggerScene) { this.triggerScene = triggerScene; }
    public String getResult() { return result; }
    public void setResult(String result) { this.result = result; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getEngine() { return engine; }
    public void setEngine(String engine) { this.engine = engine; }
    public Integer getRetryCount() { return retryCount; }
    public void setRetryCount(Integer retryCount) { this.retryCount = retryCount; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }
    public String getScreenshotPath() { return screenshotPath; }
    public void setScreenshotPath(String screenshotPath) { this.screenshotPath = screenshotPath; }
    public String getErrorMessageText() { return errorMessageText; }
    public void setErrorMessageText(String errorMessageText) { this.errorMessageText = errorMessageText; }
    public Integer getPriority() { return priority; }
    public void setPriority(Integer priority) { this.priority = priority; }
    public String getFailureReason() { return failureReason; }
    public void setFailureReason(String failureReason) { this.failureReason = failureReason; }
    public String getProxySource() { return proxySource; }
    public void setProxySource(String proxySource) { this.proxySource = proxySource; }
    public LocalDateTime getQueuedAt() { return queuedAt; }
    public void setQueuedAt(LocalDateTime queuedAt) { this.queuedAt = queuedAt; }
    public LocalDateTime getStartedAt() { return startedAt; }
    public void setStartedAt(LocalDateTime startedAt) { this.startedAt = startedAt; }
    public LocalDateTime getFinishedAt() { return finishedAt; }
    public void setFinishedAt(LocalDateTime finishedAt) { this.finishedAt = finishedAt; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
