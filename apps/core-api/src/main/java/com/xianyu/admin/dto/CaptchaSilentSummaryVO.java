package com.xianyu.admin.dto;

/**
 * 滑块求解"用户不在场时自动求解"摘要 VO。
 *
 * 仅统计自动触发场景（ws_connect / cookie_keepalive / token_refresh），
 * 排除手动触发（manual / manual_retry）。
 *
 * 用于前台进入页面时显著展示"您不在场时，滑块求解已自动为您解决 N 次"的惊喜提示。
 */
public class CaptchaSilentSummaryVO {
    /** 起始时间（ISO yyyy-MM-dd'T'HH:mm:ss），来自前端的 since 参数 */
    private String since;
    /** 截止时间（ISO yyyy-MM-dd'T'HH:mm:ss），服务端处理时的当前时间 */
    private String until;
    /** 自动触发求解总次数（含成功/失败/进行中） */
    private long total;
    /** 自动触发且成功的次数（status = 'success'） */
    private long success;
    /** 自动触发且失败的次数（status = 'fail'） */
    private long fail;
    /** 涉及的账号数（去重） */
    private long accountCount;
    /** 最近一次自动求解的时间（ISO yyyy-MM-dd HH:mm:ss），无记录时为 null */
    private String lastSolveTime;

    public String getSince() { return since; }
    public void setSince(String since) { this.since = since; }
    public String getUntil() { return until; }
    public void setUntil(String until) { this.until = until; }
    public long getTotal() { return total; }
    public void setTotal(long total) { this.total = total; }
    public long getSuccess() { return success; }
    public void setSuccess(long success) { this.success = success; }
    public long getFail() { return fail; }
    public void setFail(long fail) { this.fail = fail; }
    public long getAccountCount() { return accountCount; }
    public void setAccountCount(long accountCount) { this.accountCount = accountCount; }
    public String getLastSolveTime() { return lastSolveTime; }
    public void setLastSolveTime(String lastSolveTime) { this.lastSolveTime = lastSolveTime; }
}
