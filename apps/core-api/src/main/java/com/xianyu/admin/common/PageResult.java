package com.xianyu.admin.common;

import java.util.List;

public class PageResult<T> {
    private List<T> records;
    private long current;
    private long size;
    private long total;

    public PageResult() {}
    public PageResult(List<T> records, long current, long size, long total) {
        this.records = records; this.current = current; this.size = size; this.total = total;
    }
    public List<T> getRecords() { return records; }
    public void setRecords(List<T> records) { this.records = records; }
    public long getCurrent() { return current; }
    public void setCurrent(long current) { this.current = current; }
    public long getSize() { return size; }
    public void setSize(long size) { this.size = size; }
    public long getTotal() { return total; }
    public void setTotal(long total) { this.total = total; }
}
