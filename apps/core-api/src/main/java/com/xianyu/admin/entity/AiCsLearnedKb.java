package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "ai_cs_learned_kb")
public class AiCsLearnedKb {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "category_id")
    private Long categoryId;

    @Column(name = "question", nullable = false, length = 1000)
    private String question;

    @Lob
    @Column(name = "answer", nullable = false)
    private String answer;

    @Column(name = "tags", length = 512)
    private String tags;

    @Column(name = "source_summary", length = 500)
    private String sourceSummary;

    @Column(name = "content_hash", nullable = false, length = 32)
    private String contentHash;

    @Column(name = "score", nullable = false)
    private Integer score = 50;

    @Column(name = "review_status", nullable = false, length = 16)
    private String reviewStatus = "pending";

    @Column(name = "reviewed_by")
    private Long reviewedBy;

    @Column(name = "reviewed_time")
    private LocalDateTime reviewedTime;

    @Column(name = "reject_reason", length = 255)
    private String rejectReason;

    @Column(name = "enabled", nullable = false)
    private Integer enabled = 1;

    @Column(name = "vector_indexed", nullable = false)
    private Integer vectorIndexed = 0;

    @Column(name = "vector_error", length = 255)
    private String vectorError;

    @Column(name = "source_count", nullable = false)
    private Integer sourceCount = 1;

    @Column(name = "source_conv_ids", columnDefinition = "TEXT")
    private String sourceConvIds;

    @Column(name = "learn_batch_id", nullable = false, length = 64)
    private String learnBatchId;

    @Column(name = "sensitive_filtered", nullable = false)
    private Integer sensitiveFiltered = 1;

    @Column(name = "deleted", nullable = false)
    private Integer deleted = 0;

    @Column(name = "created_time", nullable = false, updatable = false)
    private LocalDateTime createdTime = LocalDateTime.now();

    @Column(name = "updated_time", nullable = false)
    private LocalDateTime updatedTime = LocalDateTime.now();

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getCategoryId() {
        return categoryId;
    }

    public void setCategoryId(Long categoryId) {
        this.categoryId = categoryId;
    }

    public String getQuestion() {
        return question;
    }

    public void setQuestion(String question) {
        this.question = question;
    }

    public String getAnswer() {
        return answer;
    }

    public void setAnswer(String answer) {
        this.answer = answer;
    }

    public String getTags() {
        return tags;
    }

    public void setTags(String tags) {
        this.tags = tags;
    }

    public String getSourceSummary() {
        return sourceSummary;
    }

    public void setSourceSummary(String sourceSummary) {
        this.sourceSummary = sourceSummary;
    }

    public String getContentHash() {
        return contentHash;
    }

    public void setContentHash(String contentHash) {
        this.contentHash = contentHash;
    }

    public Integer getScore() {
        return score;
    }

    public void setScore(Integer score) {
        this.score = score;
    }

    public String getReviewStatus() {
        return reviewStatus;
    }

    public void setReviewStatus(String reviewStatus) {
        this.reviewStatus = reviewStatus;
    }

    public Long getReviewedBy() {
        return reviewedBy;
    }

    public void setReviewedBy(Long reviewedBy) {
        this.reviewedBy = reviewedBy;
    }

    public LocalDateTime getReviewedTime() {
        return reviewedTime;
    }

    public void setReviewedTime(LocalDateTime reviewedTime) {
        this.reviewedTime = reviewedTime;
    }

    public String getRejectReason() {
        return rejectReason;
    }

    public void setRejectReason(String rejectReason) {
        this.rejectReason = rejectReason;
    }

    public Integer getEnabled() {
        return enabled;
    }

    public void setEnabled(Integer enabled) {
        this.enabled = enabled;
    }

    public Integer getVectorIndexed() {
        return vectorIndexed;
    }

    public void setVectorIndexed(Integer vectorIndexed) {
        this.vectorIndexed = vectorIndexed;
    }

    public String getVectorError() {
        return vectorError;
    }

    public void setVectorError(String vectorError) {
        this.vectorError = vectorError;
    }

    public Integer getSourceCount() {
        return sourceCount;
    }

    public void setSourceCount(Integer sourceCount) {
        this.sourceCount = sourceCount;
    }

    public String getSourceConvIds() {
        return sourceConvIds;
    }

    public void setSourceConvIds(String sourceConvIds) {
        this.sourceConvIds = sourceConvIds;
    }

    public String getLearnBatchId() {
        return learnBatchId;
    }

    public void setLearnBatchId(String learnBatchId) {
        this.learnBatchId = learnBatchId;
    }

    public Integer getSensitiveFiltered() {
        return sensitiveFiltered;
    }

    public void setSensitiveFiltered(Integer sensitiveFiltered) {
        this.sensitiveFiltered = sensitiveFiltered;
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

    public LocalDateTime getUpdatedTime() {
        return updatedTime;
    }

    public void setUpdatedTime(LocalDateTime updatedTime) {
        this.updatedTime = updatedTime;
    }
}
