package com.xianyu.admin.dto;

/**
 * 发货规则VO
 */
public class DeliveryRuleVO {
    private Long id;
    private Long accountId;
    private Long goodsId;
    private String ruleName;
    private String deliveryType;
    private Long cardGroupId;
    private String deliveryContent;
    private String triggerKeyword;
    private Integer status;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public Long getGoodsId() { return goodsId; }
    public void setGoodsId(Long goodsId) { this.goodsId = goodsId; }
    public String getRuleName() { return ruleName; }
    public void setRuleName(String ruleName) { this.ruleName = ruleName; }
    public String getDeliveryType() { return deliveryType; }
    public void setDeliveryType(String deliveryType) { this.deliveryType = deliveryType; }
    public Long getCardGroupId() { return cardGroupId; }
    public void setCardGroupId(Long cardGroupId) { this.cardGroupId = cardGroupId; }
    public String getDeliveryContent() { return deliveryContent; }
    public void setDeliveryContent(String deliveryContent) { this.deliveryContent = deliveryContent; }
    public String getTriggerKeyword() { return triggerKeyword; }
    public void setTriggerKeyword(String triggerKeyword) { this.triggerKeyword = triggerKeyword; }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
}
