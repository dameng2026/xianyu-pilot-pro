package com.xianyu.admin.dto;

/**
 * 维护模式状态 VO
 * <p>由 Redis 中的 xianyu:maintenance:* 键驱动，供前端轮询决定是否展示维护横幅。
 */
public class MaintenanceStatusVO {

    /** 是否处于维护中 */
    private boolean enabled;

    /** 维护提示文案，缺省时由前端使用默认文案 */
    private String message;

    /** 预计结束时间（ISO 字符串），缺省时前端显示"预计一小时内" */
    private String until;

    public MaintenanceStatusVO() {}

    public MaintenanceStatusVO(boolean enabled, String message, String until) {
        this.enabled = enabled;
        this.message = message;
        this.until = until;
    }

    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }

    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }

    public String getUntil() { return until; }
    public void setUntil(String until) { this.until = until; }
}
