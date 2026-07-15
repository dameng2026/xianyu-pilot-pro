package com.xianyu.admin.dto;

/**
 * 闲鱼交易订单DTO（更新）
 */
public class XianyuTradeOrderDTO {
    private Integer orderStatus;
    private String buyerName;
    private String buyerId;

    public Integer getOrderStatus() { return orderStatus; }
    public void setOrderStatus(Integer orderStatus) { this.orderStatus = orderStatus; }
    public String getBuyerName() { return buyerName; }
    public void setBuyerName(String buyerName) { this.buyerName = buyerName; }
    public String getBuyerId() { return buyerId; }
    public void setBuyerId(String buyerId) { this.buyerId = buyerId; }
}
