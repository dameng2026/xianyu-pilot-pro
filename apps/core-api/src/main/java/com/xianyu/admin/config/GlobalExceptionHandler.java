package com.xianyu.admin.config;

import com.xianyu.admin.common.BizException;
import com.xianyu.admin.common.Result;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;
import java.util.stream.Collectors;

@RestControllerAdvice
public class GlobalExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    @ExceptionHandler(BizException.class)
    public ResponseEntity<Result<Object>> handleBiz(BizException e) {
        Result<Object> body = new Result<>(e.getCode(), e.getMessage(), e.getData());
        return ResponseEntity.status(toHttpStatus(e.getCode(), HttpStatus.BAD_REQUEST)).body(body);
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Result<Void>> handleValidation(MethodArgumentNotValidException e) {
        List<String> errors = e.getBindingResult().getFieldErrors().stream()
                .map(this::formatFieldError)
                .distinct()
                .collect(Collectors.toList());
        if (errors.isEmpty()) {
            errors = e.getBindingResult().getGlobalErrors().stream()
                    .map(err -> err.getDefaultMessage() == null ? "请求参数不正确" : err.getDefaultMessage())
                    .distinct()
                    .collect(Collectors.toList());
        }
        return ResponseEntity.badRequest().body(new Result<>(400, String.join("；", errors), null));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<Result<Void>> handleConstraintViolation(ConstraintViolationException e) {
        String message = e.getConstraintViolations().stream()
                .map(ConstraintViolation::getMessage)
                .distinct()
                .collect(Collectors.joining("；"));
        return ResponseEntity.badRequest().body(
                new Result<>(400, message.isBlank() ? "请求参数不正确" : message, null));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Result<Void>> handleBadJson(HttpMessageNotReadableException e) {
        return ResponseEntity.badRequest().body(new Result<>(400, "请求体格式不正确", null));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Result<Void>> handleIllegalArg(IllegalArgumentException e) {
        return ResponseEntity.badRequest().body(new Result<>(400, e.getMessage(), null));
    }

    @ExceptionHandler(NoHandlerFoundException.class)
    public ResponseEntity<Result<Void>> handleNotFound(NoHandlerFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new Result<>(404, "请求的接口不存在: " + e.getRequestURL(), null));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<Result<Void>> handleNoResource(NoResourceFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new Result<>(404, "请求的资源不存在", null));
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<Result<Void>> handleMethodNotSupported(HttpRequestMethodNotSupportedException e) {
        return ResponseEntity.status(HttpStatus.METHOD_NOT_ALLOWED)
                .body(new Result<>(405, "请求方法不被支持: " + e.getMethod(), null));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Result<Void>> handle(Exception e) {
        String traceId = MDC.get(TraceIdFilter.MDC_KEY);
        if (traceId == null || traceId.isBlank()) {
            traceId = java.util.UUID.randomUUID().toString().replace("-", "");
        }
        log.error("Unhandled exception, traceId={}, errorType={}", traceId, e.getClass().getSimpleName(), e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Result.fail("系统繁忙，请稍后重试，错误编号：" + traceId));
    }

    @ExceptionHandler(EmptyResultDataAccessException.class)
    public ResponseEntity<Result<Void>> handleEmptyResult(EmptyResultDataAccessException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new Result<>(404, "请求的数据不存在或已被删除", null));
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Result<Void>> handleDataAccess(DataAccessException e) {
        String traceId = MDC.get(TraceIdFilter.MDC_KEY);
        if (traceId == null || traceId.isBlank()) {
            traceId = java.util.UUID.randomUUID().toString().replace("-", "");
        }
        log.error("Database operation unavailable, traceId={}, errorType={}", traceId, e.getClass().getSimpleName(), e);
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(new Result<>(503, "数据服务暂时不可用，请稍后重试，错误编号：" + traceId, null));
    }

    private String formatFieldError(FieldError err) {
        return err.getDefaultMessage() == null ? err.getField() + "不正确" : err.getDefaultMessage();
    }

    private HttpStatusCode toHttpStatus(int code, HttpStatus fallback) {
        if (code >= 400 && code <= 599) {
            return HttpStatusCode.valueOf(code);
        }
        return fallback;
    }
}
