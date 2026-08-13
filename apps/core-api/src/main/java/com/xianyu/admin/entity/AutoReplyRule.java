package com.xianyu.admin.entity;

import jakarta.persistence.*;

/**
 * 自动回复规则实体
 */
@Entity
@Table(name = "auto_reply_rule")
public class AutoReplyRule extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "xy_goods_id")
    private String xyGoodsId;

    @Column(name = "rule_name")
    private String ruleName;

    /**
     * 匹配类型：keyword/ai/all
     */
    @Column(name = "match_type")
    private String matchType;

    @Column(name = "match_keywords", columnDefinition = "TEXT")
    private String matchKeywords;

    @Column(name = "reply_content", columnDefinition = "TEXT")
    private String replyContent;

    @Column(name = "reply_image")
    private String replyImage;

    /**
     * 回复模式：keyword/ai
     */
    @Column(name = "reply_mode")
    private String replyMode;

    /**
     * 状态：1启用 0禁用
     */
    @Column(name = "status")
    private Integer status;

    @Column(name = "priority")
    private Integer priority;

    @Column(name = "safe_mode")
    private Integer safeMode;

    @Column(name = "handoff_keywords", columnDefinition = "TEXT")
    private String handoffKeywords;

    @Column(name = "price_floor")
    private java.math.BigDecimal priceFloor;

    @Column(name = "max_daily_replies")
    private Integer maxDailyReplies;

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

    public String getXyGoodsId() { return xyGoodsId; }
    public void setXyGoodsId(String xyGoodsId) { this.xyGoodsId = xyGoodsId; }

    public String getRuleName() {
        return ruleName;
    }

    public void setRuleName(String ruleName) {
        this.ruleName = ruleName;
    }

    public String getMatchType() {
        return matchType;
    }

    public void setMatchType(String matchType) {
        this.matchType = matchType;
    }

    public String getMatchKeywords() {
        return matchKeywords;
    }

    public void setMatchKeywords(String matchKeywords) {
        this.matchKeywords = matchKeywords;
    }

    public String getReplyContent() {
        return replyContent;
    }

    public void setReplyContent(String replyContent) {
        this.replyContent = replyContent;
    }

    public String getReplyImage() { return replyImage; }
    public void setReplyImage(String replyImage) { this.replyImage = replyImage; }

    public String getReplyMode() {
        return replyMode;
    }

    public void setReplyMode(String replyMode) {
        this.replyMode = replyMode;
    }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }

    public Integer getPriority() {
        return priority;
    }

    public void setPriority(Integer priority) {
        this.priority = priority;
    }

    public Integer getSafeMode() { return safeMode; }
    public void setSafeMode(Integer safeMode) { this.safeMode = safeMode; }
    public String getHandoffKeywords() { return handoffKeywords; }
    public void setHandoffKeywords(String handoffKeywords) { this.handoffKeywords = handoffKeywords; }
    public java.math.BigDecimal getPriceFloor() { return priceFloor; }
    public void setPriceFloor(java.math.BigDecimal priceFloor) { this.priceFloor = priceFloor; }
    public Integer getMaxDailyReplies() { return maxDailyReplies; }
    public void setMaxDailyReplies(Integer maxDailyReplies) { this.maxDailyReplies = maxDailyReplies; }
}
