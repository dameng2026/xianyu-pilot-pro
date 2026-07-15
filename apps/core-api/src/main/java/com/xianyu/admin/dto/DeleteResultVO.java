package com.xianyu.admin.dto;

import com.fasterxml.jackson.annotation.JsonInclude;

/**
 * 商品删除结果反馈VO
 */
@JsonInclude(JsonInclude.Include.NON_NULL)
public class DeleteResultVO {

    /** 数据库删除是否成功 */
    private boolean dbDeleted;

    /** 闲鱼平台删除是否成功 */
    private boolean platformDeleted;

    /** 闲鱼平台删除重试次数 */
    private int platformRetryCount;

    /** 平台删除失败时的错误信息 */
    private String platformError;

    /** 操作日志ID */
    private Long operationLogId;

    public DeleteResultVO() {}

    public static DeleteResultVO success(boolean dbDeleted, boolean platformDeleted) {
        DeleteResultVO vo = new DeleteResultVO();
        vo.dbDeleted = dbDeleted;
        vo.platformDeleted = platformDeleted;
        vo.platformRetryCount = 0;
        return vo;
    }

    public static DeleteResultVO partialSuccess(boolean dbDeleted, int retryCount, String platformError) {
        DeleteResultVO vo = new DeleteResultVO();
        vo.dbDeleted = dbDeleted;
        vo.platformDeleted = false;
        vo.platformRetryCount = retryCount;
        vo.platformError = platformError;
        return vo;
    }

    public boolean isDbDeleted() { return dbDeleted; }
    public void setDbDeleted(boolean dbDeleted) { this.dbDeleted = dbDeleted; }

    public boolean isPlatformDeleted() { return platformDeleted; }
    public void setPlatformDeleted(boolean platformDeleted) { this.platformDeleted = platformDeleted; }

    public int getPlatformRetryCount() { return platformRetryCount; }
    public void setPlatformRetryCount(int platformRetryCount) { this.platformRetryCount = platformRetryCount; }

    public String getPlatformError() { return platformError; }
    public void setPlatformError(String platformError) { this.platformError = platformError; }

    public Long getOperationLogId() { return operationLogId; }
    public void setOperationLogId(Long operationLogId) { this.operationLogId = operationLogId; }
}