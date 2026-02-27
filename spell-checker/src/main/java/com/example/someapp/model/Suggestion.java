package com.example.someapp.model;

public class Suggestion {

    private String word;
    private String translation;

    public Suggestion(String word, String translation) {
        this.word = word;
        this.translation = translation;
    }

    public String getWord() { return word; }
    public String getTranslation() { return translation; }
}
