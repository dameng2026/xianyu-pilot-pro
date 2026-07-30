package com.xianyu.admin.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.math.BigDecimal;

/**
 * 卡片组DTO（创建/更新）
 */
public class CardGroupDTO {
    @NotBlank(message = "卡密组名称不能为空")
    @Size(max = 80, message = "卡密组名称不能超过80个字符")
    private String groupName;

    @Size(max = 500, message = "卡密组描述不能超过500个字符")
    private String description;

    @Size(max = 50, message = "卡密类型不能超过50个字符")
    private String cardType;

    @Size(max = 100, message = "卡号前缀不能超过100个字符")
    private String cardPrefix;

    @Size(max = 100, message = "密码前缀不能超过100个字符")
    private String passwordPrefix;

    @Size(max = 1000, message = "备注不能超过1000个字符")
    private String remark;

    @Min(value = 0, message = "预警阈值不能小于0")
    @Max(value = 999999, message = "预警阈值过大")
    private Integer alertThreshold;

    private BigDecimal costPrice;

    private BigDecimal suggestedPrice;

    @Min(value = 0, message = "总数不能小于0")
    @Max(value = 999999, message = "总数过大")
    private Integer totalCount;

    @Min(value = 0, message = "已使用数量不能小于0")
    @Max(value = 999999, message = "已使用数量过大")
    private Integer usedCount;

    @Min(value = 0, message = "剩余数量不能小于0")
    @Max(value = 999999, message = "剩余数量过大")
    private Integer remainCount;

    @Min(value = 0, message = "状态值不正确")
    @Max(value = 1, message = "状态值不正确")
    private Integer status;

    @Size(max = 512, message = "SKU规格键不能超过512个字符")
    private String skuPropertyKey;

    public String getGroupName() { return groupName; }
    public void setGroupName(String groupName) { this.groupName = trimToNull(groupName); }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = trimToNull(description); }
    public String getCardType() { return cardType; }
    public void setCardType(String cardType) { this.cardType = trimToNull(cardType); }
    public String getCardPrefix() { return cardPrefix; }
    public void setCardPrefix(String cardPrefix) { this.cardPrefix = trimToNull(cardPrefix); }
    public String getPasswordPrefix() { return passwordPrefix; }
    public void setPasswordPrefix(String passwordPrefix) { this.passwordPrefix = trimToNull(passwordPrefix); }
    public String getRemark() { return remark; }
    public void setRemark(String remark) { this.remark = trimToNull(remark); }
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
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }

    public String getSkuPropertyKey() { return skuPropertyKey; }
    public void setSkuPropertyKey(String skuPropertyKey) { this.skuPropertyKey = trimToNull(skuPropertyKey); }

    private static String trimToNull(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
