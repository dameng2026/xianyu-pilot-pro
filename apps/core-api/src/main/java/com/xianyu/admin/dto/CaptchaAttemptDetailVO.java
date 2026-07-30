package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 滑块求解单次尝试明细 VO（用于后台查看某次求解记录的每次尝试详情）。
 */
public class CaptchaAttemptDetailVO {
    private Integer attemptNo;
    private String solveScheme;
    private String dragMethod;
    private String speedStrategy;
    private Boolean success;
    private Long durationMs;
    private String errorMessage;
    private LocalDateTime createdAt;

    public Integer getAttemptNo() { return attemptNo; }
    public void setAttemptNo(Integer attemptNo) { this.attemptNo = attemptNo; }
    public String getSolveScheme() { return solveScheme; }
    public void setSolveScheme(String solveScheme) { this.solveScheme = solveScheme; }
    public String getDragMethod() { return dragMethod; }
    public void setDragMethod(String dragMethod) { this.dragMethod = dragMethod; }
    public String getSpeedStrategy() { return speedStrategy; }
    public void setSpeedStrategy(String speedStrategy) { this.speedStrategy = speedStrategy; }
    public Boolean getSuccess() { return success; }
    public void setSuccess(Boolean success) { this.success = success; }
    public Long getDurationMs() { return durationMs; }
    public void setDurationMs(Long durationMs) { this.durationMs = durationMs; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
