package com.xianyu.admin.dto;

import java.util.List;

/**
 * 滑块求解统计 VO（KPI + 趋势 + 账号分组）。
 */
public class CaptchaSolveStatsVO {
    private Kpi kpi;
    private List<TrendPoint> trend;
    private List<AccountGroup> accounts;

    public Kpi getKpi() { return kpi; }
    public void setKpi(Kpi kpi) { this.kpi = kpi; }
    public List<TrendPoint> getTrend() { return trend; }
    public void setTrend(List<TrendPoint> trend) { this.trend = trend; }
    public List<AccountGroup> getAccounts() { return accounts; }
    public void setAccounts(List<AccountGroup> accounts) { this.accounts = accounts; }

    public static class Kpi {
        private long total;
        private long success;
        private long fail;
        private long timeout;
        private long precheckRejected;
        private long serviceUnavailable;
        /** 成功率 0~1 */
        private double successRate;

        public long getTotal() { return total; }
        public void setTotal(long total) { this.total = total; }
        public long getSuccess() { return success; }
        public void setSuccess(long success) { this.success = success; }
        public long getFail() { return fail; }
        public void setFail(long fail) { this.fail = fail; }
        public long getTimeout() { return timeout; }
        public void setTimeout(long timeout) { this.timeout = timeout; }
        public long getPrecheckRejected() { return precheckRejected; }
        public void setPrecheckRejected(long precheckRejected) { this.precheckRejected = precheckRejected; }
        public long getServiceUnavailable() { return serviceUnavailable; }
        public void setServiceUnavailable(long serviceUnavailable) { this.serviceUnavailable = serviceUnavailable; }
        public double getSuccessRate() { return successRate; }
        public void setSuccessRate(double successRate) { this.successRate = successRate; }
    }

    public static class TrendPoint {
        private String date;
        private long total;
        private long success;
        private long fail;
        private long timeout;
        private long precheckRejected;
        private long serviceUnavailable;
        private double successRate;

        public String getDate() { return date; }
        public void setDate(String date) { this.date = date; }
        public long getTotal() { return total; }
        public void setTotal(long total) { this.total = total; }
        public long getSuccess() { return success; }
        public void setSuccess(long success) { this.success = success; }
        public long getFail() { return fail; }
        public void setFail(long fail) { this.fail = fail; }
        public long getTimeout() { return timeout; }
        public void setTimeout(long timeout) { this.timeout = timeout; }
        public long getPrecheckRejected() { return precheckRejected; }
        public void setPrecheckRejected(long precheckRejected) { this.precheckRejected = precheckRejected; }
        public long getServiceUnavailable() { return serviceUnavailable; }
        public void setServiceUnavailable(long serviceUnavailable) { this.serviceUnavailable = serviceUnavailable; }
        public double getSuccessRate() { return successRate; }
        public void setSuccessRate(double successRate) { this.successRate = successRate; }
    }

    public static class AccountGroup {
        private Long accountId;
        private String accountName;
        private long total;
        private long success;
        private long fail;
        private long timeout;
        private long precheckRejected;
        private long serviceUnavailable;
        private double successRate;
        private String lastSolveTime;

        public Long getAccountId() { return accountId; }
        public void setAccountId(Long accountId) { this.accountId = accountId; }
        public String getAccountName() { return accountName; }
        public void setAccountName(String accountName) { this.accountName = accountName; }
        public long getTotal() { return total; }
        public void setTotal(long total) { this.total = total; }
        public long getSuccess() { return success; }
        public void setSuccess(long success) { this.success = success; }
        public long getFail() { return fail; }
        public void setFail(long fail) { this.fail = fail; }
        public long getTimeout() { return timeout; }
        public void setTimeout(long timeout) { this.timeout = timeout; }
        public long getPrecheckRejected() { return precheckRejected; }
        public void setPrecheckRejected(long precheckRejected) { this.precheckRejected = precheckRejected; }
        public long getServiceUnavailable() { return serviceUnavailable; }
        public void setServiceUnavailable(long serviceUnavailable) { this.serviceUnavailable = serviceUnavailable; }
        public double getSuccessRate() { return successRate; }
        public void setSuccessRate(double successRate) { this.successRate = successRate; }
        public String getLastSolveTime() { return lastSolveTime; }
        public void setLastSolveTime(String lastSolveTime) { this.lastSolveTime = lastSolveTime; }
    }
}
