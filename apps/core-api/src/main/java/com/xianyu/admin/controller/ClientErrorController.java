package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.ClientErrorService;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class ClientErrorController {
    private final ClientErrorService clientErrorService;

    public ClientErrorController(ClientErrorService clientErrorService) {
        this.clientErrorService = clientErrorService;
    }

    @PostMapping("/api/client-errors")
    public Result<Map<String, Object>> report(@RequestBody(required = false) Map<String, Object> payload,
                                              @RequestHeader(value = "Authorization", required = false) String authorization,
                                              @RequestHeader(value = "User-Agent", required = false) String userAgent,
                                              HttpServletRequest request) {
        return Result.ok(clientErrorService.report(payload == null ? Map.of() : payload, authorization, clientIp(request), userAgent));
    }


    @GetMapping("/admin-api/client-errors/page")
    public Result<PageResult<Map<String, Object>>> page(@RequestParam(defaultValue = "1") int current,
                                                        @RequestParam(defaultValue = "20") int size,
                                                        @RequestParam(required = false) String keyword,
                                                        @RequestParam(required = false) String type) {
        return Result.ok(clientErrorService.page(current, size, keyword, type));
    }

    private String clientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }
}
