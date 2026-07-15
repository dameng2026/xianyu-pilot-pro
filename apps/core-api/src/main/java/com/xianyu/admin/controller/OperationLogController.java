package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.PageUtils;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.CsvCellEncoder;
import com.xianyu.admin.entity.OperationLog;
import com.xianyu.admin.mapper.OperationLogMapper;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import org.springframework.web.bind.annotation.GetMapping;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * 操作审计日志查询接口。
 * 用于第二阶段对高风险操作（商品删除、会话转接/结束、Cookie更新等）进行可追溯复盘。
 */
@RestController
@RequestMapping({"/api/operation-logs", "/admin-api/operation-logs"})
public class OperationLogController {
    private final OperationLogMapper operationLogMapper;

    public OperationLogController(OperationLogMapper operationLogMapper) {
        this.operationLogMapper = operationLogMapper;
    }

    @GetMapping
    public Result<PageResult<OperationLog>> page(@RequestParam(required = false) String operationType,
                                                 @RequestParam(required = false) String targetType,
                                                 @RequestParam(required = false) Long targetId,
                                                 @RequestParam(required = false) String keyword,
                                                 @RequestParam(defaultValue = "1") int current,
                                                 @RequestParam(defaultValue = "20") int size) {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        int page = PageUtils.normalizeCurrent(current);
        int limit = PageUtils.normalizeSize(size);
        int offset = (page - 1) * limit;
        int total = operationLogMapper.countFiltered(tenantId, userId, operationType, targetType, targetId, keyword);
        List<OperationLog> records = operationLogMapper.listFiltered(
                tenantId, userId, operationType, targetType, targetId, keyword, offset, limit);
        return Result.ok(new PageResult<>(records, page, limit, total));
    }

    @GetMapping(value = "/export", produces = "text/csv;charset=UTF-8")
    public void exportCsv(@RequestParam(required = false) String operationType,
                          @RequestParam(required = false) String targetType,
                          @RequestParam(required = false) Long targetId,
                          @RequestParam(required = false) String keyword,
                          @RequestParam(defaultValue = "5000") int limit,
                          HttpServletResponse response) throws IOException {
        Long tenantId = TenantContext.getCurrentTenantId();
        Long userId = UserContext.userId();
        int safeLimit = Math.max(1, Math.min(limit, 5000));
        List<OperationLog> records = operationLogMapper.listFiltered(
                tenantId, userId, operationType, targetType, targetId, keyword, 0, safeLimit);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("text/csv;charset=UTF-8");
        response.setHeader("Content-Disposition", "attachment; filename=operation-logs.csv");
        StringBuilder csv = new StringBuilder("\uFEFF");
        csv.append("id,tenantId,userId,operationType,operationDesc,targetType,targetId,ipAddress,createdTime\n");
        for (OperationLog row : records) {
            csv.append(csv(row.getId())).append(',')
                    .append(csv(row.getTenantId())).append(',')
                    .append(csv(row.getUserId())).append(',')
                    .append(csv(row.getOperationType())).append(',')
                    .append(csv(row.getOperationDesc())).append(',')
                    .append(csv(row.getTargetType())).append(',')
                    .append(csv(row.getTargetId())).append(',')
                    .append(csv(row.getIpAddress())).append(',')
                    .append(csv(row.getCreatedTime()))
                    .append('\n');
        }
        response.getWriter().write(csv.toString());
    }

    private String csv(Object value) {
        return CsvCellEncoder.encode(value);
    }
}
