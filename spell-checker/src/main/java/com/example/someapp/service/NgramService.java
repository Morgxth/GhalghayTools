package com.example.someapp.service;

import com.example.someapp.model.ContextWarning;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;

import java.io.InputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Service
public class NgramService {

    // Флагуем биграммы, если ожидаемое кол-во совместных вхождений >= 1 (но не встречались)
    // expected = freq(w1) * freq(w2) / totalTokens
    private static final double MIN_EXPECTED_COUNT = 1.0;

    private Map<String, Integer> unigrams;
    private Map<String, Integer> bigrams;
    private int vocabularySize;
    private int totalTokens;

    @PostConstruct
    @SuppressWarnings("unchecked")
    public void loadModel() {
        try (InputStream is = getClass().getResourceAsStream("/ngram/ingush_ngrams.json")) {
            ObjectMapper mapper = new ObjectMapper();
            Map<String, Object> data = mapper.readValue(is, new TypeReference<>() {});
            unigrams = (Map<String, Integer>) data.get("unigrams");
            bigrams  = (Map<String, Integer>) data.get("bigrams");
            vocabularySize = unigrams.size();
            totalTokens = ((Number) data.get("totalTokens")).intValue();
        } catch (Exception e) {
            throw new RuntimeException("Не удалось загрузить N-gram модель", e);
        }
    }

    /**
     * Анализирует текст и возвращает биграммы с подозрительно низкой вероятностью.
     * Использует Laplace (add-1) сглаживание.
     */
    public List<ContextWarning> analyzeContext(String text) {
        String[] words = text.toLowerCase().split("\\s+");
        List<ContextWarning> warnings = new ArrayList<>();

        for (int i = 1; i < words.length; i++) {
            String w1 = SpellCheckService.normalizePalochka(words[i - 1]);
            String w2 = SpellCheckService.normalizePalochka(words[i]);

            int f1 = unigrams.getOrDefault(w1, 0);
            int f2 = unigrams.getOrDefault(w2, 0);

            // Флагуем только если статистически ожидали увидеть пару хотя бы 1 раз,
            // но она вообще не встречалась в корпусе
            double expected = (double) f1 * f2 / totalTokens;
            if (expected < MIN_EXPECTED_COUNT) continue;

            String bigramKey = w1 + " " + w2;
            if (!bigrams.containsKey(bigramKey)) {
                warnings.add(new ContextWarning(bigramKey, i, bigramScore(w1, w2)));
            }
        }

        return warnings;
    }

    public int getBigramCount() {
        return bigrams.size();
    }

    public int getFrequency(String word) {
        return unigrams.getOrDefault(word, 0);
    }

    /**
     * P(w2 | w1) с Laplace сглаживанием:
     * (count(w1, w2) + 1) / (count(w1) + |V|)
     */
    private double bigramScore(String w1, String w2) {
        int bigramCount  = bigrams.getOrDefault(w1 + " " + w2, 0);
        int unigramCount = unigrams.getOrDefault(w1, 0);
        return (bigramCount + 1.0) / (unigramCount + vocabularySize);
    }
}
