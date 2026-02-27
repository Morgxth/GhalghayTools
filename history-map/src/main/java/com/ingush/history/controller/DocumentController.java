package com.ingush.history.controller;

import com.ingush.history.model.Document;
import com.ingush.history.repository.DocumentRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/documents")
@RequiredArgsConstructor
public class DocumentController {

    private final DocumentRepository documentRepository;

    @GetMapping
    public List<Document> getDocuments(
            @RequestParam(required = false) Integer year_from,
            @RequestParam(required = false) Integer year_to) {

        if (year_from != null && year_to != null) {
            return documentRepository.findByYearBetween(year_from, year_to);
        }
        return documentRepository.findAll();
    }

    @GetMapping("/{id}")
    public Document getDocument(@PathVariable Long id) {
        return documentRepository.findById(id)
                .orElseThrow(() -> new RuntimeException("Document not found: " + id));
    }
}
