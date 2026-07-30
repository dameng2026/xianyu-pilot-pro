package com.xianyu.admin.dto;

import java.util.List;

/**
 * 滑块求解尝试明细成功率统计 VO。
 *
 * 数据来源：xianyu_captcha_solve_attempt 表（每次 attempt 一条记录）。
 * 按求解方案、拖动方法、速度策略、尝试轮次四个维度聚合统计成功率。
 *
 * 用于后台「成功率统计」tab 展示，便于分析各方案的实际效果，淘汰低成功率方案。
 */
public class CaptchaAttemptStatsVO {
    /** 按求解方案聚合（python_script / playwright） */
    private List<DimensionStat> bySolveScheme;
    /** 按拖动方法聚合（in_container / out_container / none） */
    private List<DimensionStat> byDragMethod;
    /** 按速度策略聚合（standard / medium / fast / slow_pause / random / none） */
    private List<DimensionStat> bySpeedStrategy;
    /** 按尝试轮次聚合（1-5） */
    private List<AttemptNoStat> byAttemptNo;
    /** 总尝试次数 */
    private long totalAttempts;
    /** 总成功次数 */
    private long totalSuccess;
    /** 整体成功率 0~100 */
    private double overallSuccessRate;
    /** 统计天数 */
    private int days;
    /** 账号 ID（0=不限账号） */
    private long accountId;

    public List<DimensionStat> getBySolveScheme() { return bySolveScheme; }
    public void setBySolveScheme(List<DimensionStat> bySolveScheme) { this.bySolveScheme = bySolveScheme; }
    public List<DimensionStat> getByDragMethod() { return byDragMethod; }
    public void setByDragMethod(List<DimensionStat> byDragMethod) { this.byDragMethod = byDragMethod; }
    public List<DimensionStat> getBySpeedStrategy() { return bySpeedStrategy; }
    public void setBySpeedStrategy(List<DimensionStat> bySpeedStrategy) { this.bySpeedStrategy = bySpeedStrategy; }
    public List<AttemptNoStat> getByAttemptNo() { return byAttemptNo; }
    public void setByAttemptNo(List<AttemptNoStat> byAttemptNo) { this.byAttemptNo = byAttemptNo; }
    public long getTotalAttempts() { return totalAttempts; }
    public void setTotalAttempts(long totalAttempts) { this.totalAttempts = totalAttempts; }
    public long getTotalSuccess() { return totalSuccess; }
    public void setTotalSuccess(long totalSuccess) { this.totalSuccess = totalSuccess; }
    public double getOverallSuccessRate() { return overallSuccessRate; }
    public void setOverallSuccessRate(double overallSuccessRate) { this.overallSuccessRate = overallSuccessRate; }
    public int getDays() { return days; }
    public void setDays(int days) { this.days = days; }
    public long getAccountId() { return accountId; }
    public void setAccountId(long accountId) { this.accountId = accountId; }

    /** 通用维度统计（scheme/method/strategy 共用） */
    public static class DimensionStat {
        /** 维度名（如 'playwright' / 'in_container' / 'standard'） */
        private String dim;
        /** 总次数 */
        private long total;
        /** 成功次数 */
        private long success;
        /** 成功率 0~100 */
        private double successRate;
        /** 平均耗时（毫秒） */
        private long avgDurationMs;

        public String getDim() { return dim; }
        public void setDim(String dim) { this.dim = dim; }
        public long getTotal() { return total; }
        public void setTotal(long total) { this.total = total; }
        public long getSuccess() { return success; }
        public void setSuccess(long success) { this.success = success; }
        public double getSuccessRate() { return successRate; }
        public void setSuccessRate(double successRate) { this.successRate = successRate; }
        public long getAvgDurationMs() { return avgDurationMs; }
        public void setAvgDurationMs(long avgDurationMs) { this.avgDurationMs = avgDurationMs; }
    }

    /** 按尝试轮次聚合（dim 字段改名为 attemptNo） */
    public static class AttemptNoStat {
        /** 尝试轮次编号（1-5） */
        private int attemptNo;
        private long total;
        private long success;
        private double successRate;
        private long avgDurationMs;

        public int getAttemptNo() { return attemptNo; }
        public void setAttemptNo(int attemptNo) { this.attemptNo = attemptNo; }
        public long getTotal() { return total; }
        public void setTotal(long total) { this.total = total; }
        public long getSuccess() { return success; }
        public void setSuccess(long success) { this.success = success; }
        public double getSuccessRate() { return successRate; }
        public void setSuccessRate(double successRate) { this.successRate = successRate; }
        public long getAvgDurationMs() { return avgDurationMs; }
        public void setAvgDurationMs(long avgDurationMs) { this.avgDurationMs = avgDurationMs; }
    }
}
