package com.getjobs.application.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.servlet.NoHandlerFoundException;
import java.util.Map;
import java.util.HashMap;
import java.util.UUID;
import java.time.Instant;
import java.net.UnknownHostException;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> handleAllExceptions(Exception e) {
        String errorId = UUID.randomUUID().toString().substring(0, 8);

        // 日志记录完整堆栈（仅在服务端）
        System.err.println("[" + errorId + "] " + e.getClass().getName() + ": " + e.getMessage());
        e.printStackTrace();

        Map<String, Object> response = new HashMap<>();
        response.put("error", "InternalServerError");
        response.put("errorId", errorId);
        response.put("timestamp", Instant.now().toString());
        // 不再暴露堆栈跟踪到客户端
        response.put("message", sanitizeMessage(e.getMessage()));

        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }

    @ExceptionHandler(UnknownHostException.class)
    public ResponseEntity<Map<String, Object>> handleUnknownHost(UnknownHostException e) {
        Map<String, Object> response = new HashMap<>();
        response.put("error", "ServiceUnavailable");
        response.put("message", "无法连接到目标服务器，请检查网络");
        response.put("timestamp", Instant.now().toString());
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(response);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, Object>> handleIllegalArgument(IllegalArgumentException e) {
        Map<String, Object> response = new HashMap<>();
        response.put("error", "BadRequest");
        response.put("message", sanitizeMessage(e.getMessage()));
        response.put("timestamp", Instant.now().toString());
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response);
    }

    @ExceptionHandler(NoHandlerFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(NoHandlerFoundException e) {
        Map<String, Object> response = new HashMap<>();
        response.put("error", "NotFound");
        response.put("message", "请求的资源不存在");
        response.put("timestamp", Instant.now().toString());
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(response);
    }

    @ExceptionHandler(org.springframework.web.HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<Map<String, Object>> handleMethodNotSupported(
            org.springframework.web.HttpRequestMethodNotSupportedException e) {
        Map<String, Object> response = new HashMap<>();
        response.put("error", "MethodNotAllowed");
        response.put("message", "不支持的请求方法");
        response.put("timestamp", Instant.now().toString());
        return ResponseEntity.status(HttpStatus.METHOD_NOT_ALLOWED).body(response);
    }

    /**
     * 清理错误消息，防止敏感信息泄漏
     */
    private String sanitizeMessage(String message) {
        if (message == null) {
            return "An unexpected error occurred";
        }
        // 移除文件路径、IP地址、堆栈片段等敏感信息
        String sanitized = message
                .replaceAll("[A-Za-z]:\\\\[^\\s]+", "[path]")
                .replaceAll("\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}", "[ip]")
                .replaceAll("http://[^\\s]+", "[url]")
                .replaceAll("Caused by:[^\\n]+", "Caused by: [hidden]");

        // 限制消息长度
        if (sanitized.length() > 200) {
            sanitized = sanitized.substring(0, 200) + "...";
        }
        return sanitized;
    }
}
