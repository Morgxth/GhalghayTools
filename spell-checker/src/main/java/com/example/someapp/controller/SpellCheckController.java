package com.example.someapp.controller;

import com.example.someapp.model.ContextWarning;
import com.example.someapp.model.SpellCheckRequest;
import com.example.someapp.model.SpellCheckResponse;
import com.example.someapp.service.NgramService;
import com.example.someapp.service.SpellCheckService;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.List;
import java.util.Map;

@Tag(name = "Spell Check", description = "Проверка орфографии ингушского языка")
@RestController
@RequestMapping("/api/spell-check")
public class SpellCheckController {

    private final SpellCheckService spellCheckService;
    private final NgramService ngramService;

    public SpellCheckController(SpellCheckService spellCheckService, NgramService ngramService) {
        this.spellCheckService = spellCheckService;
        this.ngramService = ngramService;
    }

    @Operation(summary = "Проверить орфографию", description = "Принимает ингушский текст, возвращает список ошибок и контекстных предупреждений. Лимит: 30 запросов/мин.")
    @PostMapping
    public ResponseEntity<SpellCheckResponse> check(@RequestBody SpellCheckRequest request) {
        if (request.getText() == null || request.getText().isBlank()) {
            return ResponseEntity.badRequest().build();
        }

        String text = request.getText();
        SpellCheckResponse spellResult = spellCheckService.check(text);
        List<ContextWarning> contextWarnings = ngramService.analyzeContext(text);

        return ResponseEntity.ok(new SpellCheckResponse(
                spellResult.isHasErrors() || !contextWarnings.isEmpty(),
                spellResult.getCorrections(),
                contextWarnings
        ));
    }

    @Operation(summary = "Поиск по словарю", description = "Постраничный поиск по словарю с фильтром по наличию перевода.")
    @GetMapping("/dictionary")
    public ResponseEntity<Map<String, Object>> dictionary(
            @RequestParam(defaultValue = "") String q,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "50") int size,
            @RequestParam(defaultValue = "false") boolean onlyWithTranslation) {
        return ResponseEntity.ok(spellCheckService.getDictionary(q, page, size, onlyWithTranslation));
    }

    @Operation(summary = "Карточка слова", description = "Возвращает перевод, частоту в корпусе и однокоренные слова.")
    @GetMapping("/dictionary/{word}")
    public ResponseEntity<Map<String, Object>> wordCard(@PathVariable String word) {
        return ResponseEntity.ok(spellCheckService.getWordCard(word));
    }

    @Operation(summary = "Предложить перевод", description = "Отправляет предложение перевода в очередь модерации (файл suggestions.jsonl).")
    @PostMapping("/suggestions")
    public ResponseEntity<Map<String, String>> suggest(@RequestBody Map<String, String> body) {
        String word        = body.getOrDefault("word", "").strip();
        String translation = body.getOrDefault("translation", "").strip();
        String comment     = body.getOrDefault("comment", "").strip();

        if (word.isEmpty() || translation.isEmpty()) {
            return ResponseEntity.badRequest().body(Map.of("error", "word и translation обязательны"));
        }

        Map<String, Object> entry = Map.of(
                "word", word,
                "translation", translation,
                "comment", comment,
                "timestamp", Instant.now().toString()
        );

        String suggestionsFile = Paths.get(System.getProperty("user.dir"), "suggestions.jsonl").toString();
        try (FileWriter fw = new FileWriter(suggestionsFile, true)) {
            fw.write(new ObjectMapper().writeValueAsString(entry) + "\n");
        } catch (IOException e) {
            return ResponseEntity.internalServerError().body(Map.of("error", "Не удалось сохранить"));
        }

        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    @Operation(summary = "Статус сервиса", description = "Возвращает размер словаря и количество биграмм.")
    @GetMapping("/status")
    public ResponseEntity<Map<String, Object>> status() {
        return ResponseEntity.ok(Map.of(
                "status", "ok",
                "dictionarySize", spellCheckService.getDictionarySize(),
                "bigramCount", ngramService.getBigramCount()
        ));
    }
}
