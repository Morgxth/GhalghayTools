package com.ingush.history.controller;

import com.ingush.history.model.Society;
import com.ingush.history.repository.SocietyRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/societies")
@RequiredArgsConstructor
public class SocietyController {

    private final SocietyRepository societyRepository;

    @GetMapping
    public List<Society> getSocieties() {
        return societyRepository.findAll();
    }

    @GetMapping("/{id}")
    public Society getSociety(@PathVariable Long id) {
        return societyRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Society not found: " + id));
    }
}
