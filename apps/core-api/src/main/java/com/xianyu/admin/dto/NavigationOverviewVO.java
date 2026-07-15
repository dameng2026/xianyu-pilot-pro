package com.xianyu.admin.dto;

/**
 * 导航概览VO
 */
public class NavigationOverviewVO {

    private Integer accountCount;
    private Integer goodsCount;
    private Integer todayOrderCount;
    private Integer messageCount;
    private Integer pendingCount;

    public Integer getAccountCount() { return accountCount != null ? accountCount : 0; }
    public void setAccountCount(Integer accountCount) { this.accountCount = accountCount; }

    public Integer getGoodsCount() { return goodsCount != null ? goodsCount : 0; }
    public void setGoodsCount(Integer goodsCount) { this.goodsCount = goodsCount; }

    public Integer getTodayOrderCount() { return todayOrderCount != null ? todayOrderCount : 0; }
    public void setTodayOrderCount(Integer todayOrderCount) { this.todayOrderCount = todayOrderCount; }

    public Integer getMessageCount() { return messageCount != null ? messageCount : 0; }
    public void setMessageCount(Integer messageCount) { this.messageCount = messageCount; }

    public Integer getPendingCount() { return pendingCount != null ? pendingCount : 0; }
    public void setPendingCount(Integer pendingCount) { this.pendingCount = pendingCount; }
}
