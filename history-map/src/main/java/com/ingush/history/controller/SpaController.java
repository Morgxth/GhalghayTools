package com.ingush.history.controller;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/**
 * Перенаправляет React Router маршруты на index.html.
 *
 * ВАЖНО: не используем wildcard /** — он перехватил бы
 * статику (/assets/index.js, /icon.svg и т.д.).
 * Перечисляем только конкретные SPA-пути приложения.
 */
@Controller
public class SpaController {

    @GetMapping(value = { "/timeline", "/encyclopedia", "/archive", "/about" })
    public String forward() {
        return "forward:/index.html";
    }
}
