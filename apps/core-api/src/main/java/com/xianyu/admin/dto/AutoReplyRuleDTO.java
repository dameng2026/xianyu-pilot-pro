package com.xianyu.admin.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * 自动回复规则DTO（创建/更新）
 */
public class AutoReplyRuleDTO {
    @NotNull(message = "请选择闲鱼账号")
    private Long accountId;

    @Size(max = 64, message = "商品ID不能超过64个字符")
    private String xyGoodsId;

    @NotBlank(message = "规则名称不能为空")
    @Size(max = 80, message = "规则名称不能超过80个字符")
    private String ruleName;

    @NotBlank(message = "匹配模式不能为空")
    @Pattern(regexp = "any|all|regex|ai", message = "匹配模式不正确")
    private String matchType;

    @Size(max = 1000, message = "匹配关键词不能超过1000个字符")
    private String matchKeywords;

    @Size(max = 5000, message = "回复内容不能超过5000个字符")
    private String replyContent;

    @Size(max = 500, message = "回复图片地址不能超过500个字符")
    private String replyImage;

    @NotBlank(message = "回复模式不能为空")
    @Pattern(regexp = "text|ai", message = "回复模式不正确")
    private String replyMode;

    @Min(value = 0, message = "状态值不正确")
    @Max(value = 1, message = "状态值不正确")
    private Integer status;

    @Min(value = 0, message = "优先级不能小于0")
    @Max(value = 9999, message = "优先级过大")
    private Integer priority;

    @Min(value = 0, message = "安全模式值不正确")
    @Max(value = 1, message = "安全模式值不正确")
    private Integer safeMode;

    @Size(max = 1000, message = "人工接管关键词不能超过1000个字符")
    private String handoffKeywords;

    @DecimalMin(value = "0.00", message = "最低价不能小于0")
    private java.math.BigDecimal priceFloor;

    @Min(value = 0, message = "每日回复上限不能小于0")
    @Max(value = 10000, message = "每日回复上限过大")
    private Integer maxDailyReplies;

    @AssertTrue(message = "非AI匹配模式必须填写匹配关键词")
    public boolean isMatchKeywordsValid() {
        return "ai".equalsIgnoreCase(matchType) || (matchKeywords != null && !matchKeywords.trim().isEmpty());
    }

    @AssertTrue(message = "回复内容与回复图片不能同时为空")
    public boolean isReplyPayloadValid() {
        if ("ai".equalsIgnoreCase(replyMode)) {
            return replyContent != null && !replyContent.trim().isEmpty();
        }
        return (replyContent != null && !replyContent.trim().isEmpty())
            || (replyImage != null && !replyImage.trim().isEmpty());
    }

    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getXyGoodsId() { return xyGoodsId; }
    public void setXyGoodsId(String xyGoodsId) { this.xyGoodsId = xyGoodsId; }
    public String getRuleName() { return ruleName; }
    public void setRuleName(String ruleName) { this.ruleName = trimToNull(ruleName); }
    public String getMatchType() { return matchType; }
    public void setMatchType(String matchType) { this.matchType = trimToNull(matchType); }
    public String getMatchKeywords() { return matchKeywords; }
    public void setMatchKeywords(String matchKeywords) { this.matchKeywords = trimToNull(matchKeywords); }
    public String getReplyContent() { return replyContent; }
    public void setReplyContent(String replyContent) { this.replyContent = trimToNull(replyContent); }
    public String getReplyImage() { return replyImage; }
    public void setReplyImage(String replyImage) { this.replyImage = trimToNull(replyImage); }
    public String getReplyMode() { return replyMode; }
    public void setReplyMode(String replyMode) { this.replyMode = trimToNull(replyMode); }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
    public Integer getPriority() { return priority; }
    public void setPriority(Integer priority) { this.priority = priority; }
    public Integer getSafeMode() { return safeMode; }
    public void setSafeMode(Integer safeMode) { this.safeMode = safeMode; }
    public String getHandoffKeywords() { return handoffKeywords; }
    public void setHandoffKeywords(String handoffKeywords) { this.handoffKeywords = trimToNull(handoffKeywords); }
    public java.math.BigDecimal getPriceFloor() { return priceFloor; }
    public void setPriceFloor(java.math.BigDecimal priceFloor) { this.priceFloor = priceFloor; }
    public Integer getMaxDailyReplies() { return maxDailyReplies; }
    public void setMaxDailyReplies(Integer maxDailyReplies) { this.maxDailyReplies = maxDailyReplies; }

    private static String trimToNull(String value) {
        if (value == null) return null;
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
