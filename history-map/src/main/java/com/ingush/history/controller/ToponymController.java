package com.ingush.history.controller;

import com.ingush.history.model.Toponym;
import com.ingush.history.repository.ToponymRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/toponyms")
@RequiredArgsConstructor
public class ToponymController {

    private final ToponymRepository toponymRepository;

    @GetMapping
    public List<Toponym> getToponyms(@RequestParam(required = false) String search) {
        if (search != null && !search.isBlank()) {
            return toponymRepository.findByNameRuContainingIgnoreCase(search);
        }
        return toponymRepository.findAll();
    }

    @GetMapping("/{id}")
    public Toponym getToponym(@PathVariable Long id) {
        return toponymRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Toponym not found: " + id));
    }
}
