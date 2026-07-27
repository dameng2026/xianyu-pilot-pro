package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "ai_cs_kb_learning_log")
public class AiCsKbLearningLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "batch_id", nullable = false, length = 64)
    private String batchId;

    @Column(name = "started_at", nullable = false)
    private LocalDateTime startedAt;

    @Column(name = "finished_at")
    private LocalDateTime finishedAt;

    @Column(name = "status", nullable = false, length = 16)
    private String status;  // running/success/failed/partial

    @Column(name = "total_conversations", nullable = false)
    private Integer totalConversations = 0;

    @Column(name = "kept_conversations", nullable = false)
    private Integer keptConversations = 0;

    @Column(name = "rejected_by_ai_ratio", nullable = false)
    private Integer rejectedByAiRatio = 0;

    @Column(name = "extracted_items", nullable = false)
    private Integer extractedItems = 0;

    @Column(name = "deduplicated_items", nullable = false)
    private Integer deduplicatedItems = 0;

    @Column(name = "llm_tokens_used", nullable = false)
    private Integer llmTokensUsed = 0;

    @Column(name = "llm_cost_yuan", nullable = false, precision = 10, scale = 4)
    private BigDecimal llmCostYuan = BigDecimal.ZERO;

    @Lob
    @Column(name = "error_message")
    private String errorMessage;

    @Lob
    @Column(name = "config_snapshot", columnDefinition = "JSON")
    private String configSnapshot;

    @Column(name = "deleted", nullable = false)
    private Integer deleted = 0;

    @Column(name = "created_time", nullable = false, updatable = false)
    private LocalDateTime createdTime = LocalDateTime.now();

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getBatchId() {
        return batchId;
    }

    public void setBatchId(String batchId) {
        this.batchId = batchId;
    }

    public LocalDateTime getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(LocalDateTime startedAt) {
        this.startedAt = startedAt;
    }

    public LocalDateTime getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(LocalDateTime finishedAt) {
        this.finishedAt = finishedAt;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public Integer getTotalConversations() {
        return totalConversations;
    }

    public void setTotalConversations(Integer totalConversations) {
        this.totalConversations = totalConversations;
    }

    public Integer getKeptConversations() {
        return keptConversations;
    }

    public void setKeptConversations(Integer keptConversations) {
        this.keptConversations = keptConversations;
    }

    public Integer getRejectedByAiRatio() {
        return rejectedByAiRatio;
    }

    public void setRejectedByAiRatio(Integer rejectedByAiRatio) {
        this.rejectedByAiRatio = rejectedByAiRatio;
    }

    public Integer getExtractedItems() {
        return extractedItems;
    }

    public void setExtractedItems(Integer extractedItems) {
        this.extractedItems = extractedItems;
    }

    public Integer getDeduplicatedItems() {
        return deduplicatedItems;
    }

    public void setDeduplicatedItems(Integer deduplicatedItems) {
        this.deduplicatedItems = deduplicatedItems;
    }

    public Integer getLlmTokensUsed() {
        return llmTokensUsed;
    }

    public void setLlmTokensUsed(Integer llmTokensUsed) {
        this.llmTokensUsed = llmTokensUsed;
    }

    public BigDecimal getLlmCostYuan() {
        return llmCostYuan;
    }

    public void setLlmCostYuan(BigDecimal llmCostYuan) {
        this.llmCostYuan = llmCostYuan;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public String getConfigSnapshot() {
        return configSnapshot;
    }

    public void setConfigSnapshot(String configSnapshot) {
        this.configSnapshot = configSnapshot;
    }

    public Integer getDeleted() {
        return deleted;
    }

    public void setDeleted(Integer deleted) {
        this.deleted = deleted;
    }

    public LocalDateTime getCreatedTime() {
        return createdTime;
    }

    public void setCreatedTime(LocalDateTime createdTime) {
        this.createdTime = createdTime;
    }
}
