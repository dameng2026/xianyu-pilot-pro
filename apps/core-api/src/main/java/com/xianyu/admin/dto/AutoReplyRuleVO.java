package com.xianyu.admin.dto;

/**
 * 自动回复规则VO
 */
public class AutoReplyRuleVO {
    private Long id;
    private Long accountId;
    private String xyGoodsId;
    private String ruleName;
    private String matchType;
    private String matchKeywords;
    private String replyContent;
    private String replyImage;
    private String replyMode;
    private Integer status;
    private Integer priority;
    private Integer safeMode;
    private String handoffKeywords;
    private java.math.BigDecimal priceFloor;
    private Integer maxDailyReplies;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    public Long getAccountId() { return accountId; }
    public void setAccountId(Long accountId) { this.accountId = accountId; }
    public String getXyGoodsId() { return xyGoodsId; }
    public void setXyGoodsId(String xyGoodsId) { this.xyGoodsId = xyGoodsId; }
    public String getRuleName() { return ruleName; }
    public void setRuleName(String ruleName) { this.ruleName = ruleName; }
    public String getMatchType() { return matchType; }
    public void setMatchType(String matchType) { this.matchType = matchType; }
    public String getMatchKeywords() { return matchKeywords; }
    public void setMatchKeywords(String matchKeywords) { this.matchKeywords = matchKeywords; }
    public String getReplyContent() { return replyContent; }
    public void setReplyContent(String replyContent) { this.replyContent = replyContent; }
    public String getReplyImage() { return replyImage; }
    public void setReplyImage(String replyImage) { this.replyImage = replyImage; }
    public String getReplyMode() { return replyMode; }
    public void setReplyMode(String replyMode) { this.replyMode = replyMode; }
    public Integer getStatus() { return status; }
    public void setStatus(Integer status) { this.status = status; }
    public Integer getPriority() { return priority; }
    public void setPriority(Integer priority) { this.priority = priority; }
    public Integer getSafeMode() { return safeMode; }
    public void setSafeMode(Integer safeMode) { this.safeMode = safeMode; }
    public String getHandoffKeywords() { return handoffKeywords; }
    public void setHandoffKeywords(String handoffKeywords) { this.handoffKeywords = handoffKeywords; }
    public java.math.BigDecimal getPriceFloor() { return priceFloor; }
    public void setPriceFloor(java.math.BigDecimal priceFloor) { this.priceFloor = priceFloor; }
    public Integer getMaxDailyReplies() { return maxDailyReplies; }
    public void setMaxDailyReplies(Integer maxDailyReplies) { this.maxDailyReplies = maxDailyReplies; }
}
