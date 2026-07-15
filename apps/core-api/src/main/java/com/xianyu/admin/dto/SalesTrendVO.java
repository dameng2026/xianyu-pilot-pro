package com.xianyu.admin.dto;

import java.util.ArrayList;
import java.util.List;

/**
 * 销售趋势VO
 */
public class SalesTrendVO {

    private List<String> dates;
    private List<Integer> orderCount;
    private List<Integer> messageCount;
    private List<Integer> deliveryCount;
    private List<Integer> deliverySuccess;
    private List<Integer> deliveryFail;
    private List<Integer> aiReplyCount;

    public SalesTrendVO() {
        this.dates = new ArrayList<>();
        this.orderCount = new ArrayList<>();
        this.messageCount = new ArrayList<>();
        this.deliveryCount = new ArrayList<>();
        this.deliverySuccess = new ArrayList<>();
        this.deliveryFail = new ArrayList<>();
        this.aiReplyCount = new ArrayList<>();
    }

    public List<String> getDates() { return dates; }
    public void setDates(List<String> dates) { this.dates = dates; }

    public List<Integer> getOrderCount() { return orderCount; }
    public void setOrderCount(List<Integer> orderCount) { this.orderCount = orderCount; }

    public List<Integer> getMessageCount() { return messageCount; }
    public void setMessageCount(List<Integer> messageCount) { this.messageCount = messageCount; }

    public List<Integer> getDeliveryCount() { return deliveryCount; }
    public void setDeliveryCount(List<Integer> deliveryCount) { this.deliveryCount = deliveryCount; }

    public List<Integer> getDeliverySuccess() { return deliverySuccess; }
    public void setDeliverySuccess(List<Integer> deliverySuccess) { this.deliverySuccess = deliverySuccess; }

    public List<Integer> getDeliveryFail() { return deliveryFail; }
    public void setDeliveryFail(List<Integer> deliveryFail) { this.deliveryFail = deliveryFail; }

    public List<Integer> getAiReplyCount() { return aiReplyCount; }
    public void setAiReplyCount(List<Integer> aiReplyCount) { this.aiReplyCount = aiReplyCount; }
}
