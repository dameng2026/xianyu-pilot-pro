package com.xianyu.admin.dto;

import java.math.BigDecimal;

/**
 * 卡片组VO
 */
public class CardGroupVO {
    private Long id;
    private String groupName;
    private String description;
    private String cardType;
    private String cardPrefix;
    private String passwordPrefix;
    private String remark;
    private Integer alertThreshold;
    private BigDecimal costPrice;
    private BigDecimal suggestedPrice;
    private Integer totalCount;
    private Integer usedCount;
    private Integer remainCount;
    private Integer lockedCount;
    private Integer invalidCount;
    private Integer errorCount;
    private Integer status;
    private String skuPropertyKey;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public String getGroupName() { return groupName; }
    public void setGroupName(String groupName) { this.groupName = groupName; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public String getCardType() { return cardType; }
    public void setCardType(String cardType) { this.cardType = cardType; }
    public String getCardPrefix() { return cardPrefix; }
    public void setCardPrefix(String cardPrefix) { this.cardPrefix = cardPrefix; }
    public String getPasswordPrefix() { return passwordPrefix; }
    public void setPasswordPrefix(String passwordPrefix) { this.passwordPrefix = passwordPrefix; }
    public String getRemark() { return remark; }
    public void setRemark(String remark) { this.remark = remark; }
    public Integer getAlertThreshold() { return alertThreshold; }
    public void setAlertThreshold(Integer alertThreshold) { this.alertThreshold = alertThreshold; }
    public BigDecimal getCostPrice() { return costPrice; }
    public void setCostPrice(BigDecimal costPrice) { this.costPrice = costPrice; }
    public BigDecimal getSuggestedPrice() { return suggestedPrice; }
    public void setSuggestedPrice(BigDecimal suggestedPrice) { this.suggestedPrice = suggestedPrice; }
    public Integer getTotalCount() { return totalCount; }
    public void setTotalCount(Integer totalCount) { this.totalCount = totalCount; }
    public Integer getUsedCount() { return usedCount; }
    public void setUsedCount(Integer usedCount) { this.usedCount = usedCount; }
    public Integer getRemainCount() { return remainCount; }
    public void setRemainCount(Integer remainCount) { this.remainCount = remainCount; }
    public Integer getLockedCount() { return lockedCount; }
    public void setLockedCount(Integer lockedCount) { this.lockedCount = lockedCount; }
    public Integer getInvalidCount() { return invalidCount; }
    public void setInvalidCount(Integer invalidCount) { this.invalidCount = invalidCount; }
    public Integer getErrorCount() { return errorCount; }
    public void setErrorCount(Integer errorCount) { this.errorCount = errorCount; }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
    public String getSkuPropertyKey() { return skuPropertyKey; }
    public void setSkuPropertyKey(String skuPropertyKey) { this.skuPropertyKey = skuPropertyKey; }
}
