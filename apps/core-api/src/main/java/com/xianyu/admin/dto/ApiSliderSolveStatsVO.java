package com.xianyu.admin.dto;

import java.util.List;
import java.util.Map;

public record ApiSliderSolveStatsVO(
        Map<String, Object> kpi, List<Map<String, Object>> trend, List<Map<String, Object>> tenants
) {}
