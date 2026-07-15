package com.xianyu.admin.dto;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 发货规则DTO（创建/更新）
 */
public class DeliveryRuleDTO {
    @NotNull(message = "请选择闲鱼账号")
    private Long accountId;
    private Long goodsId;

    @NotBlank(message = "规则名称不能为空")
    @Size(max = 80, message = "规则名称不能超过80个字符")
    private String ruleName;

    @NotBlank(message = "发货类型不能为空")
    @Pattern(regexp = "card|text", message = "当前仅支持文本或卡密发货")
    private String deliveryType;

    private Long cardGroupId;

    @Size(max = 5000, message = "发货内容不能超过5000个字符")
    private String deliveryContent;

    @Size(max = 200, message = "触发关键词不能超过200个字符")
    private String triggerKeyword;

    @Min(value = 0, message = "状态值不正确")
    @Max(value = 1, message = "状态值不正确")
    private Integer status;

    @AssertTrue(message = "卡密发货必须选择卡密组")
    public boolean isCardDeliveryValid() {
        return !"card".equalsIgnoreCase(deliveryType) || cardGroupId != null;
    }

    @AssertTrue(message = "文本发货内容不能为空")
    public boolean isTextDeliveryValid() {
        return !"text".equalsIgnoreCase(deliveryType) || (deliveryContent != null && !deliveryContent.trim().isEmpty());
    }

    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public Long getGoodsId() { return goodsId; }
    public void setGoodsId(Long goodsId) { this.goodsId = goodsId; }
    public String getRuleName() { return ruleName; }
    public void setRuleName(String ruleName) { this.ruleName = trimToNull(ruleName); }
    public String getDeliveryType() { return deliveryType; }
    public void setDeliveryType(String deliveryType) { this.deliveryType = trimToNull(deliveryType); }
    public Long getCardGroupId() { return cardGroupId; }
    public void setCardGroupId(Long cardGroupId) { this.cardGroupId = cardGroupId; }
    public String getDeliveryContent() { return deliveryContent; }
    public void setDeliveryContent(String deliveryContent) { this.deliveryContent = trimToNull(deliveryContent); }
    public String getTriggerKeyword() { return triggerKeyword; }
    public void setTriggerKeyword(String triggerKeyword) { this.triggerKeyword = trimToNull(triggerKeyword); }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }

    private static String trimToNull(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
