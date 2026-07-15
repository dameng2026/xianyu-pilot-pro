package com.xianyu.admin.controller;

import com.xianyu.admin.common.PageResult;
import com.xianyu.admin.common.Result;
import com.xianyu.admin.common.BizException;
import com.xianyu.admin.service.PaymentService;
import com.xianyu.admin.security.AdminContext;
import com.xianyu.admin.security.TenantContext;
import com.xianyu.admin.security.UserContext;
import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.function.Supplier;

@RestController
public class PaymentController {
    private static final Logger log = LoggerFactory.getLogger(PaymentController.class);
    private static final Set<String> CALLBACK_CHANNELS = Set.of("alipay", "wechat");

    private final PaymentService paymentService;

    @Value("${payment.sandbox.enabled:false}")
    private boolean sandboxModeEnabled;

    public PaymentController(PaymentService paymentService) {
        this.paymentService = paymentService;
    }

    @GetMapping("/api/payment/methods")
    public Result<List<Map<String, Object>>> enabledMethods() {
        requireUserContext();
        List<Map<String, Object>> methods = callPayment("支付方式", paymentService::enabledMethods);
        if (methods == null || methods.isEmpty()) {
            throw new BizException(503, "当前暂无可用支付方式，请稍后再试");
        }
        return Result.ok(methods);
    }

    @GetMapping("/api/payment/token-plans")
    public Result<List<Map<String, Object>>> tokenPlans() {
        requireUserContext();
        List<Map<String, Object>> plans = callPayment("Token 充值套餐", paymentService::tokenPlans);
        if (plans == null || plans.isEmpty()) {
            throw new BizException(503, "当前暂无可用 Token 充值套餐，请稍后再试");
        }
        return Result.ok(plans);
    }

    @PostMapping("/api/payment/orders")
    public Result<Map<String, Object>> createOrder(@RequestBody Map<String, Object> data, HttpServletRequest request) {
        requireUserContext();
        requireBody(data, "支付订单参数不能为空");
        return Result.ok(callPayment("创建支付订单", () -> paymentService.createOrder(data, clientIp(request))));
    }

    @GetMapping("/api/payment/orders/{orderNo}")
    public Result<Map<String, Object>> orderDetail(@PathVariable String orderNo) {
        requireUserContext();
        String normalizedOrderNo = requireOrderNo(orderNo);
        return Result.ok(callPayment("支付订单", () -> paymentService.userOrderDetail(normalizedOrderNo)));
    }

    @PostMapping("/api/payment/orders/{orderNo}/close")
    public Result<Map<String, Object>> closeOrder(@PathVariable String orderNo) {
        requireUserContext();
        String normalizedOrderNo = requireOrderNo(orderNo);
        return Result.ok(callPayment("关闭支付订单", () -> paymentService.closeUserOrder(normalizedOrderNo)));
    }

    @PostMapping("/api/payment/orders/{orderNo}/mock-pay")
    public Result<Map<String, Object>> mockPayOrder(@PathVariable String orderNo) {
        requireUserContext();
        requireSandboxMode();
        String normalizedOrderNo = requireOrderNo(orderNo);
        return Result.ok(callPayment("模拟支付", () -> paymentService.mockPayUserOrder(normalizedOrderNo)));
    }

    @GetMapping("/admin-api/payment/configs")
    public Result<List<Map<String, Object>>> configs() {
        requireSuperAdmin();
        return Result.ok(callPayment("支付配置", paymentService::listConfigs));
    }

    @PostMapping("/admin-api/payment/configs")
    public Result<Map<String, Object>> saveConfig(@RequestBody Map<String, Object> data) {
        requireSuperAdmin();
        requireBody(data, "支付配置不能为空");
        return Result.ok(callPayment("保存支付配置", () -> paymentService.saveConfig(data)));
    }

    @GetMapping("/admin-api/payment/orders/page")
    public Result<PageResult<Map<String, Object>>> orderPage(@RequestParam(defaultValue = "1") int current,
                                                             @RequestParam(defaultValue = "20") int size,
                                                             @RequestParam(required = false) String keyword,
                                                             @RequestParam(required = false) String status,
                                                             @RequestParam(required = false) String orderType) {
        requireSuperAdmin();
        return Result.ok(callPayment("支付订单列表",
                () -> paymentService.pageOrders(current, size, keyword, status, orderType)));
    }

    @GetMapping("/admin-api/payment/token-plans/page")
    public Result<PageResult<Map<String, Object>>> tokenPlanPage(@RequestParam(defaultValue = "1") int current,
                                                                 @RequestParam(defaultValue = "20") int size,
                                                                 @RequestParam(required = false) String keyword,
                                                                 @RequestParam(required = false) String status) {
        requireSuperAdmin();
        return Result.ok(callPayment("Token 充值套餐列表",
                () -> paymentService.pageTokenPlans(current, size, keyword, status)));
    }

    @PostMapping("/admin-api/payment/token-plans")
    public Result<Map<String, Object>> saveTokenPlan(@RequestBody Map<String, Object> data) {
        requireSuperAdmin();
        requireBody(data, "Token 充值套餐不能为空");
        return Result.ok(callPayment("保存 Token 充值套餐", () -> paymentService.saveTokenPlan(data)));
    }

    @DeleteMapping("/admin-api/payment/token-plans/{id}")
    public Result<Void> deleteTokenPlan(@PathVariable long id) {
        requireSuperAdmin();
        if (id <= 0) {
            throw new BizException(400, "Token 充值套餐 ID 非法");
        }
        runPayment("删除 Token 充值套餐", () -> paymentService.deleteTokenPlan(id));
        return Result.ok(null);
    }

    @PostMapping(value = {"/open-api/payment/callback/{channel}", "/payment/callback/{channel}"}, consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> callback(@PathVariable String channel,
                                           @RequestBody(required = false) Map<String, Object> payload,
                                           HttpServletRequest request) {
        Map<String, Object> safePayload = payload == null ? Map.of() : payload;
        return handleCallbackRequest(channel, safePayload, String.valueOf(safePayload));
    }


    @PostMapping(value = {"/open-api/payment/callback/{channel}", "/payment/callback/{channel}"}, consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    public ResponseEntity<String> callbackForm(@PathVariable String channel,
                                               @RequestParam Map<String, String> payload) {
        Map<String, String> safePayload = payload == null ? Map.of() : payload;
        return handleCallbackRequest(
                channel,
                toObjectMap(safePayload),
                String.valueOf(safePayload));
    }


    @GetMapping({"/open-api/payment/callback/{channel}", "/payment/callback/{channel}"})
    public ResponseEntity<String> callbackGet(@PathVariable String channel,
                                              @RequestParam Map<String, String> payload) {
        Map<String, String> safePayload = payload == null ? Map.of() : payload;
        return handleCallbackRequest(
                channel,
                toObjectMap(safePayload),
                String.valueOf(safePayload));
    }

    private ResponseEntity<String> handleCallbackRequest(String channel,
                                                         Map<String, Object> payload,
                                                         String rawBody) {
        String normalizedChannel = channel == null ? "" : channel.trim().toLowerCase(Locale.ROOT);
        if (!CALLBACK_CHANNELS.contains(normalizedChannel)) {
            return ResponseEntity.badRequest().body("fail");
        }
        try {
            paymentService.handleCallback(normalizedChannel, payload, rawBody);
            return ResponseEntity.ok("success");
        } catch (BizException e) {
            int status = e.getCode() >= 400 && e.getCode() <= 499 ? e.getCode() : 503;
            log.warn("支付回调被拒绝, channel={}, status={}", normalizedChannel, status);
            return ResponseEntity.status(status).body("fail");
        } catch (Exception e) {
            log.error("支付回调处理异常, channel={}, errorType={}",
                    normalizedChannel,
                    e.getClass().getSimpleName());
            return ResponseEntity.status(503).body("fail");
        }
    }

    private void requireSuperAdmin() {
        if (AdminContext.userId() == null) {
            throw new BizException(401, "管理员登录状态已失效");
        }
        if (!AdminContext.hasRole("R_SUPER")) {
            throw new BizException(403, "无权操作支付配置");
        }
    }

    private void requireUserContext() {
        Long userId = UserContext.userId();
        Long userTenantId = UserContext.getTenantId();
        Long tenantUserId = TenantContext.getCurrentUserId();
        Long tenantId = TenantContext.getCurrentTenantId();
        if (userId == null || userTenantId == null || userTenantId <= 0
                || !Objects.equals(userId, tenantUserId)
                || !Objects.equals(userTenantId, tenantId)) {
            throw new BizException(401, "登录状态已失效，请重新登录");
        }
    }

    private void requireSandboxMode() {
        if (!sandboxModeEnabled) {
            throw new BizException(403, "支付沙箱未启用，模拟支付不可用");
        }
    }

    private void requireBody(Map<String, Object> body, String message) {
        if (body == null || body.isEmpty()) {
            throw new BizException(400, message);
        }
    }

    private String requireOrderNo(String orderNo) {
        String normalized = orderNo == null ? "" : orderNo.trim();
        if (normalized.isEmpty() || normalized.length() > 120) {
            throw new BizException(400, "支付订单号不正确");
        }
        return normalized;
    }

    private <T> T callPayment(String operation, Supplier<T> action) {
        try {
            T result = action.get();
            if (result == null) {
                throw new BizException(503, operation + "暂时不可用，请稍后重试");
            }
            return result;
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("{}失败, errorType={}", operation, e.getClass().getSimpleName());
            throw new BizException(503, operation + "暂时不可用，请稍后重试");
        }
    }

    private void runPayment(String operation, Runnable action) {
        try {
            action.run();
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.error("{}失败, errorType={}", operation, e.getClass().getSimpleName());
            throw new BizException(503, operation + "暂时不可用，请稍后重试");
        }
    }

    private Map<String, Object> toObjectMap(Map<String, String> source) {
        Map<String, Object> result = new java.util.LinkedHashMap<>();
        source.forEach(result::put);
        return result;
    }

    private String clientIp(HttpServletRequest request) {
        return com.xianyu.admin.security.ClientIpResolver.resolve(request);
    }
}
