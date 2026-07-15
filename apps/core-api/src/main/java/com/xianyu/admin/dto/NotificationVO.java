package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 通知VO
 */
public class NotificationVO {

    private Long id;
    private String title;
    private String content;
    private String type;
    private Integer status;
    private LocalDateTime createdTime;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getTitle() { return title != null ? title : ""; }
    public void setTitle(String title) { this.title = title; }

    public String getContent() { return content != null ? content : ""; }
    public void setContent(String content) { this.content = content; }

    public String getType() { return type != null ? type : ""; }
    public void setType(String type) { this.type = type; }

    public Integer getStatus() { return status != null ? status : 0; }
    public void setStatus(Integer status) { this.status = status; }

    public LocalDateTime getCreatedTime() { return createdTime; }
    public void setCreatedTime(LocalDateTime createdTime) { this.createdTime = createdTime; }
}
