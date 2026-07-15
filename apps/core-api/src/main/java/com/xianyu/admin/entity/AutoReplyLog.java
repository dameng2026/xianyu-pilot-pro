package com.xianyu.admin.entity;

import jakarta.persistence.*;

/**
 * 自动回复日志实体
 */
@Entity
@Table(name = "auto_reply_log")
public class AutoReplyLog extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "account_id")
    private Long accountId;

    @Column(name = "conversation_id")
    private Long conversationId;

    @Column(name = "rule_id")
    private Long ruleId;

    @Column(name = "trigger_message", columnDefinition = "TEXT")
    private String triggerMessage;

    @Column(name = "reply_content", columnDefinition = "TEXT")
    private String replyContent;

    /**
     * 命中类型：keyword/ai
     */
    @Column(name = "hit_type")
    private String hitType;

    /**
     * 状态：1成功 0失败
     */
    @Column(name = "status")
    private Integer status;

    @Column(name = "fail_reason")
    private String failReason;

    /**
     * 处理动作：manual/suggest_only/auto_send_allowed
     */
    @Column(name = "action")
    private String action;

    @Column(name = "safety_reasons", columnDefinition = "TEXT")
    private String safetyReasons;

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

    public Long getConversationId() {
        return conversationId;
    }

    public void setConversationId(Long conversationId) {
        this.conversationId = conversationId;
    }

    public Long getRuleId() {
        return ruleId;
    }

    public void setRuleId(Long ruleId) {
        this.ruleId = ruleId;
    }

    public String getTriggerMessage() {
        return triggerMessage;
    }

    public void setTriggerMessage(String triggerMessage) {
        this.triggerMessage = triggerMessage;
    }

    public String getReplyContent() {
        return replyContent;
    }

    public void setReplyContent(String replyContent) {
        this.replyContent = replyContent;
    }

    public String getHitType() {
        return hitType;
    }

    public void setHitType(String hitType) {
        this.hitType = hitType;
    }

    public Integer getStatus() {
        return status;
    }

    public void setStatus(Integer status) {
        this.status = status;
    }

    public String getFailReason() {
        return failReason;
    }

    public void setFailReason(String failReason) {
        this.failReason = failReason;
    }

    public String getAction() {
        return action;
    }

    public void setAction(String action) {
        this.action = action;
    }

    public String getSafetyReasons() {
        return safetyReasons;
    }

    public void setSafetyReasons(String safetyReasons) {
        this.safetyReasons = safetyReasons;
    }

}
