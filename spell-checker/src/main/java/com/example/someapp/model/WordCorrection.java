package com.example.someapp.model;

import java.util.List;

public class WordCorrection {

    private String word;
    private int position;
    private List<Suggestion> suggestions;

    public WordCorrection(String word, int position, List<Suggestion> suggestions) {
        this.word = word;
        this.position = position;
        this.suggestions = suggestions;
    }

    public String getWord() { return word; }
    public int getPosition() { return position; }
    public List<Suggestion> getSuggestions() { return suggestions; }
}
