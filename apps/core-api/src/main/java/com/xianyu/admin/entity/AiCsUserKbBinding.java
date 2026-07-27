package com.xianyu.admin.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "ai_cs_user_kb_binding",
       uniqueConstraints = @UniqueConstraint(
           name = "uk_user_kb_binding",
           columnNames = {"tenant_id", "user_id", "kb_type", "kb_id", "deleted"}))
public class AiCsUserKbBinding {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "tenant_id", nullable = false)
    private Long tenantId;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "kb_type", nullable = false, length = 16)
    private String kbType;  // learned / user

    @Column(name = "kb_id", nullable = false)
    private Long kbId;

    @Column(name = "enabled", nullable = false)
    private Integer enabled = 1;

    @Column(name = "bound_at", nullable = false, updatable = false)
    private LocalDateTime boundAt = LocalDateTime.now();

    @Column(name = "deleted", nullable = false)
    private Integer deleted = 0;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getTenantId() {
        return tenantId;
    }

    public void setTenantId(Long tenantId) {
        this.tenantId = tenantId;
    }

    public Long getUserId() {
        return userId;
    }

    public void setUserId(Long userId) {
        this.userId = userId;
    }

    public String getKbType() {
        return kbType;
    }

    public void setKbType(String kbType) {
        this.kbType = kbType;
    }

    public Long getKbId() {
        return kbId;
    }

    public void setKbId(Long kbId) {
        this.kbId = kbId;
    }

    public Integer getEnabled() {
        return enabled;
    }

    public void setEnabled(Integer enabled) {
        this.enabled = enabled;
    }

    public LocalDateTime getBoundAt() {
        return boundAt;
    }

    public void setBoundAt(LocalDateTime boundAt) {
        this.boundAt = boundAt;
    }

    public Integer getDeleted() {
        return deleted;
    }

    public void setDeleted(Integer deleted) {
        this.deleted = deleted;
    }
}
