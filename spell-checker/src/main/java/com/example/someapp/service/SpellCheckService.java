package com.example.someapp.service;

import com.example.someapp.model.SpellCheckResponse;
import com.example.someapp.model.Suggestion;
import com.example.someapp.model.WordCorrection;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import org.apache.commons.text.similarity.LevenshteinDistance;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

@Service
public class SpellCheckService {

    // Ищем совпадения с расстоянием редактирования не более 2
    private static final int MAX_DISTANCE = 2;
    private static final int MAX_SUGGESTIONS = 5;

    private final LevenshteinDistance levenshtein = new LevenshteinDistance(MAX_DISTANCE);
    private final NgramService ngramService;
    private final IngushStemmer stemmer = new IngushStemmer();
    private Set<String> dictionary = new HashSet<>();
    private Map<String, String> translations = new HashMap<>();

    public SpellCheckService(NgramService ngramService) {
        this.ngramService = ngramService;
    }

    @PostConstruct
    public void loadDictionary() {
        try (InputStream is = getClass().getResourceAsStream("/dictionary/ingush_words.txt");
             BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {

            String line;
            while ((line = reader.readLine()) != null) {
                line = line.strip();
                if (!line.isEmpty() && !line.startsWith("#")) {
                    dictionary.add(line.toLowerCase());
                }
            }
        } catch (IOException e) {
            throw new RuntimeException("Не удалось загрузить словарь", e);
        }

        try (InputStream is = getClass().getResourceAsStream("/dictionary/ingush_translations.json")) {
            if (is != null) {
                translations = new ObjectMapper().readValue(is, new TypeReference<Map<String, String>>() {});
            }
        } catch (IOException e) {
            // переводы не критичны — продолжаем без них
        }

        try (InputStream is = getClass().getResourceAsStream("/dictionary/ingush_ablaut.json")) {
            if (is != null) {
                Map<String, String> ablautMap = new ObjectMapper()
                        .readValue(is, new TypeReference<Map<String, String>>() {});
                stemmer.setAblautMap(ablautMap);
            }
        } catch (IOException e) {
            // аблаут не критичен — продолжаем без него
        }
    }

    public SpellCheckResponse check(String text) {
        text = normalizePalochka(text);
        String[] words = text.split("\\s+");
        List<WordCorrection> corrections = new ArrayList<>();

        for (int i = 0; i < words.length; i++) {
            String clean = stripPunctuation(words[i]).toLowerCase();
            if (clean.isEmpty()) continue;

            if (!dictionary.contains(clean) && !stemmer.isKnownForm(clean, dictionary)) {
                List<Suggestion> suggestions = getSuggestions(clean);
                corrections.add(new WordCorrection(words[i], i, suggestions));
            }
        }

        return new SpellCheckResponse(!corrections.isEmpty(), corrections, List.of());
    }

    public int getDictionarySize() {
        return dictionary.size();
    }

    public Map<String, Object> getDictionary(String query, int page, int size, boolean onlyWithTranslation) {
        String q = query.toLowerCase().trim();
        List<String> filtered = dictionary.stream()
                .filter(w -> q.isEmpty() || w.startsWith(q))
                .filter(w -> !onlyWithTranslation || translations.containsKey(w))
                .sorted()
                .toList();

        long total = filtered.size();
        List<Map<String, String>> words = filtered.stream()
                .skip((long) page * size)
                .limit(size)
                .map(w -> {
                    Map<String, String> entry = new HashMap<>();
                    entry.put("word", w);
                    entry.put("translation", translations.getOrDefault(w, ""));
                    return entry;
                })
                .toList();

        Map<String, Object> result = new HashMap<>();
        result.put("words", words);
        result.put("total", total);
        result.put("page", page);
        result.put("size", size);
        return result;
    }

    public Map<String, Object> getWordCard(String word) {
        word = word.toLowerCase().trim();
        String translation = translations.getOrDefault(word, "");
        int frequency = ngramService.getFrequency(word);

        // Однокоренные слова: с тем же префиксом длиной 4+
        String prefix = word.length() > 4 ? word.substring(0, 4) : word;
        String finalWord = word;
        List<String> related = dictionary.stream()
                .filter(w -> !w.equals(finalWord) && w.startsWith(prefix))
                .sorted(Comparator.comparingInt(String::length))
                .limit(6)
                .toList();

        Map<String, Object> result = new HashMap<>();
        result.put("word", word);
        result.put("inDictionary", dictionary.contains(word));
        result.put("translation", translation);
        result.put("frequency", frequency);
        result.put("related", related);
        return result;
    }

    private List<Suggestion> getSuggestions(String word) {
        return dictionary.stream()
                .filter(w -> levenshtein.apply(word, w) >= 0)
                .sorted(Comparator
                        .comparingInt((String w) -> levenshtein.apply(word, w))
                        .thenComparing(Comparator.comparingInt(
                                (String w) -> ngramService.getFrequency(w)).reversed()))
                .limit(MAX_SUGGESTIONS)
                .map(w -> new Suggestion(w, translations.get(w)))
                .toList();
    }

    /**
     * Нормализует все варианты палочки к единому символу ӏ (U+04CF).
     * В разных документах палочка встречается как:
     *   ӏ (U+04CF), Ӏ (U+04C0), цифра 1 после согласных, латинская I после согласных.
     */
    public static String normalizePalochka(String text) {
        // Заглавная палочка → строчная
        text = text.replace('\u04C0', 'ӏ');
        // Латинская I после согласных → палочка
        text = text.replaceAll("(?<=[гкхчтпбдзсфвщшцжнмлрй])I", "ӏ");
        // Цифра 1 после согласных внутри слова → палочка
        text = text.replaceAll("(?<=[гкхчтпбдзсфвщшцжнмлрй])1(?=[а-яёӏ])", "ӏ");
        return text;
    }

    private String stripPunctuation(String word) {
        return word.replaceAll("[^\\p{L}ӏ]", "");
    }
}
