package com.example.someapp.config;

import io.github.bucket4j.Bandwidth;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.Refill;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.FilterConfig;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Простой IP-based rate limiter на Bucket4j.
 * Лимит: 30 запросов/минуту на IP для POST /api/spell-check.
 */
@Component
public class RateLimitFilter implements Filter {

    // 30 токенов, пополнение 30/мин
    private static final int CAPACITY = 30;
    private static final Duration REFILL_PERIOD = Duration.ofMinutes(1);

    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest request = (HttpServletRequest) req;
        HttpServletResponse response = (HttpServletResponse) res;

        // Применяем лимит только к spell-check endpoint
        if ("POST".equalsIgnoreCase(request.getMethod())
                && request.getRequestURI().equals("/api/spell-check")) {

            String ip = getClientIp(request);
            Bucket bucket = buckets.computeIfAbsent(ip, k -> newBucket());

            if (!bucket.tryConsume(1)) {
                response.setStatus(429);
                response.setContentType("application/json");
                response.getWriter().write("{\"error\":\"Too Many Requests — лимит 30 запросов/мин\"}");
                return;
            }
        }

        chain.doFilter(req, res);
    }

    private Bucket newBucket() {
        return Bucket.builder()
                .addLimit(Bandwidth.classic(CAPACITY, Refill.greedy(CAPACITY, REFILL_PERIOD)))
                .build();
    }

    private String getClientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].strip();
        }
        return request.getRemoteAddr();
    }

    @Override public void init(FilterConfig filterConfig) {}
    @Override public void destroy() {}
}
