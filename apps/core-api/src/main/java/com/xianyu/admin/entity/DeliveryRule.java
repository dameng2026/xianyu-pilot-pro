package com.xianyu.admin.entity;

import jakarta.persistence.*;

/**
 * 发货规则实体
 */
@Entity
@Table(name = "delivery_rule")
public class DeliveryRule extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "goods_id")
    private Long goodsId;

    @Column(name = "rule_name")
    private String ruleName;

    /**
     * 发货类型：card/text
     */
    @Column(name = "delivery_type")
    private String deliveryType;


    /** 卡密组ID：delivery_type 为 card/kami 时优先从该组取卡密 */
    @Column(name = "card_group_id")
    private Long cardGroupId;

    /** 文本发货内容：delivery_type 为 text 时使用 */
    @Column(name = "delivery_content")
    private String deliveryContent;

    /** 触发关键词：为空表示付款后直接触发 */
    @Column(name = "trigger_keyword")
    private String triggerKeyword;

    /**
     * 状态：1启用 0禁用
     */
    @Column(name = "status")
    private Integer status;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getAccountId() {
        return accountId;
    }

    public void setAccountId(Long accountId) {
        this.accountId = accountId;
    }

    public Long getGoodsId() {
        return goodsId;
    }

    public void setGoodsId(Long goodsId) {
        this.goodsId = goodsId;
    }

    public String getRuleName() {
        return ruleName;
    }

    public void setRuleName(String ruleName) {
        this.ruleName = ruleName;
    }

    public String getDeliveryType() {
        return deliveryType;
    }

    public void setDeliveryType(String deliveryType) {
        this.deliveryType = deliveryType;
    }

    public Long getCardGroupId() { return cardGroupId; }

    public void setCardGroupId(Long cardGroupId) { this.cardGroupId = cardGroupId; }

    public String getDeliveryContent() { return deliveryContent; }

    public void setDeliveryContent(String deliveryContent) { this.deliveryContent = deliveryContent; }

    public String getTriggerKeyword() { return triggerKeyword; }

    public void setTriggerKeyword(String triggerKeyword) { this.triggerKeyword = triggerKeyword; }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }
}
