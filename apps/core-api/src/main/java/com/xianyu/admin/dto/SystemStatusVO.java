package com.xianyu.admin.dto;

import java.time.LocalDateTime;

/**
 * 系统状态VO
 */
public class SystemStatusVO {

    private Long id;
    private String nodeName;
    private Integer status;
    private Double cpu;
    private Double memory;
    private Double disk;
    private LocalDateTime lastHeartbeat;

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getNodeName() { return nodeName != null ? nodeName : ""; }
    public void setNodeName(String nodeName) { this.nodeName = nodeName; }

    public Integer getStatus() { return status != null ? status : 0; }
    public void setStatus(Integer status) { this.status = status; }

    public Double getCpu() { return cpu != null ? cpu : 0.0; }
    public void setCpu(Double cpu) { this.cpu = cpu; }

    public Double getMemory() { return memory != null ? memory : 0.0; }
    public void setMemory(Double memory) { this.memory = memory; }

    public Double getDisk() { return disk != null ? disk : 0.0; }
    public void setDisk(Double disk) { this.disk = disk; }

    public LocalDateTime getLastHeartbeat() { return lastHeartbeat; }
    public void setLastHeartbeat(LocalDateTime lastHeartbeat) { this.lastHeartbeat = lastHeartbeat; }
}
