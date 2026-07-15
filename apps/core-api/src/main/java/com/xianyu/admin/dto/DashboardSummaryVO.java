package com.xianyu.admin.dto;

/**
 * 仪表盘汇总统计VO
 */
public class DashboardSummaryVO {

    private Integer accountCount;
    private Integer goodsCount;
    private Integer sellingGoodsCount;
    private Integer totalSoldCount;
    private Integer todayOrderCount;
    private java.math.BigDecimal todaySalesAmount;
    private Integer messageCount;
    private Integer autoReplyCount;
    private Double wsOnlineRate;
    private Integer deliverySuccessCount;
    private Integer deliveryFailCount;
    private Integer pendingDeliveryCount;

    public Integer getAccountCount() { return accountCount != null ? accountCount : 0; }
    public void setAccountCount(Integer accountCount) { this.accountCount = accountCount; }

    public Integer getGoodsCount() { return goodsCount != null ? goodsCount : 0; }
    public void setGoodsCount(Integer goodsCount) { this.goodsCount = goodsCount; }

    public Integer getSellingGoodsCount() { return sellingGoodsCount != null ? sellingGoodsCount : 0; }
    public void setSellingGoodsCount(Integer sellingGoodsCount) { this.sellingGoodsCount = sellingGoodsCount; }

    public Integer getTotalSoldCount() { return totalSoldCount != null ? totalSoldCount : 0; }
    public void setTotalSoldCount(Integer totalSoldCount) { this.totalSoldCount = totalSoldCount; }

    public Integer getTodayOrderCount() { return todayOrderCount != null ? todayOrderCount : 0; }
    public void setTodayOrderCount(Integer todayOrderCount) { this.todayOrderCount = todayOrderCount; }

    public java.math.BigDecimal getTodaySalesAmount() { return todaySalesAmount != null ? todaySalesAmount : java.math.BigDecimal.ZERO; }
    public void setTodaySalesAmount(java.math.BigDecimal todaySalesAmount) { this.todaySalesAmount = todaySalesAmount; }

    public Integer getMessageCount() { return messageCount != null ? messageCount : 0; }
    public void setMessageCount(Integer messageCount) { this.messageCount = messageCount; }

    public Integer getAutoReplyCount() { return autoReplyCount != null ? autoReplyCount : 0; }
    public void setAutoReplyCount(Integer autoReplyCount) { this.autoReplyCount = autoReplyCount; }

    public Double getWsOnlineRate() { return wsOnlineRate != null ? wsOnlineRate : 0.0; }
    public void setWsOnlineRate(Double wsOnlineRate) { this.wsOnlineRate = wsOnlineRate; }

    public Integer getDeliverySuccessCount() { return deliverySuccessCount != null ? deliverySuccessCount : 0; }
    public void setDeliverySuccessCount(Integer deliverySuccessCount) { this.deliverySuccessCount = deliverySuccessCount; }

    public Integer getDeliveryFailCount() { return deliveryFailCount != null ? deliveryFailCount : 0; }
    public void setDeliveryFailCount(Integer deliveryFailCount) { this.deliveryFailCount = deliveryFailCount; }

    public Integer getPendingDeliveryCount() { return pendingDeliveryCount != null ? pendingDeliveryCount : 0; }
    public void setPendingDeliveryCount(Integer pendingDeliveryCount) { this.pendingDeliveryCount = pendingDeliveryCount; }
}
