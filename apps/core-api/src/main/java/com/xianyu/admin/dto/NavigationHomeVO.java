package com.xianyu.admin.dto;

import java.util.Collections;
import java.util.List;

public class NavigationHomeVO {

    private Object carousels;
    private Object announcements;
    private boolean contentAvailable = true;
    private String contentMessage = "";
    private NavigationOverviewVO overview;
    private List<NotificationVO> notifications;
    private List<SystemStatusVO> systemStatus;

    public Object getCarousels() {
        return carousels != null ? carousels : Collections.emptyList();
    }

    public void setCarousels(Object carousels) {
        this.carousels = carousels;
    }

    public Object getAnnouncements() {
        return announcements != null ? announcements : Collections.emptyList();
    }

    public void setAnnouncements(Object announcements) {
        this.announcements = announcements;
    }

    public boolean isContentAvailable() {
        return contentAvailable;
    }

    public void setContentAvailable(boolean contentAvailable) {
        this.contentAvailable = contentAvailable;
    }

    public String getContentMessage() {
        return contentMessage != null ? contentMessage : "";
    }

    public void setContentMessage(String contentMessage) {
        this.contentMessage = contentMessage;
    }

    public NavigationOverviewVO getOverview() {
        return overview != null ? overview : new NavigationOverviewVO();
    }

    public void setOverview(NavigationOverviewVO overview) {
        this.overview = overview;
    }

    public List<NotificationVO> getNotifications() {
        return notifications != null ? notifications : Collections.emptyList();
    }

    public void setNotifications(List<NotificationVO> notifications) {
        this.notifications = notifications;
    }

    public List<SystemStatusVO> getSystemStatus() {
        return systemStatus != null ? systemStatus : Collections.emptyList();
    }

    public void setSystemStatus(List<SystemStatusVO> systemStatus) {
        this.systemStatus = systemStatus;
    }
}
