package com.xianyu.admin.entity;

import jakarta.persistence.*;

import java.math.BigDecimal;

/**
 * 卡片组实体
 */
@Entity
@Table(name = "card_group")
public class CardGroup extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "group_name")
    private String groupName;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "group_type")
    private String groupType;

    @Column(name = "card_prefix")
    private String cardPrefix;

    @Column(name = "password_prefix")
    private String passwordPrefix;

    @Column(name = "remark", columnDefinition = "TEXT")
    private String remark;

    @Column(name = "alert_threshold")
    private Integer alertThreshold;

    @Column(name = "cost_price")
    private BigDecimal costPrice;

    @Column(name = "suggested_price")
    private BigDecimal suggestedPrice;

    @Column(name = "total_count")
    private Integer totalCount;

    @Column(name = "used_count")
    private Integer usedCount;

    @Column(name = "remain_count")
    private Integer remainCount;

    /**
     * SKU 专属卡密池的规格键（对应 xianyu_goods_sku.property_key）
     * 为空：通用卡密池（服务所有 SKU）
     * 非空：SKU 专属卡密池（仅服务对应 SKU）
     */
    @Column(name = "sku_property_key")
    private String skuPropertyKey;

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

    public String getGroupName() {
        return groupName;
    }

    public void setGroupName(String groupName) {
        this.groupName = groupName;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getGroupType() {
        return groupType;
    }

    public void setGroupType(String groupType) {
        this.groupType = groupType;
    }

    public String getCardPrefix() {
        return cardPrefix;
    }

    public void setCardPrefix(String cardPrefix) {
        this.cardPrefix = cardPrefix;
    }

    public String getPasswordPrefix() {
        return passwordPrefix;
    }

    public void setPasswordPrefix(String passwordPrefix) {
        this.passwordPrefix = passwordPrefix;
    }

    public String getRemark() {
        return remark;
    }

    public void setRemark(String remark) {
        this.remark = remark;
    }

    public Integer getAlertThreshold() {
        return alertThreshold;
    }

    public void setAlertThreshold(Integer alertThreshold) {
        this.alertThreshold = alertThreshold;
    }

    public BigDecimal getCostPrice() {
        return costPrice;
    }

    public void setCostPrice(BigDecimal costPrice) {
        this.costPrice = costPrice;
    }

    public BigDecimal getSuggestedPrice() {
        return suggestedPrice;
    }

    public void setSuggestedPrice(BigDecimal suggestedPrice) {
        this.suggestedPrice = suggestedPrice;
    }

    public Integer getTotalCount() {
        return totalCount;
    }

    public void setTotalCount(Integer totalCount) {
        this.totalCount = totalCount;
    }

    public Integer getUsedCount() {
        return usedCount;
    }

    public void setUsedCount(Integer usedCount) {
        this.usedCount = usedCount;
    }

    public Integer getRemainCount() {
        return remainCount;
    }

    public void setRemainCount(Integer remainCount) {
        this.remainCount = remainCount;
    }

    public String getSkuPropertyKey() {
        return skuPropertyKey;
    }

    public void setSkuPropertyKey(String skuPropertyKey) {
        this.skuPropertyKey = skuPropertyKey;
    }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }
}
