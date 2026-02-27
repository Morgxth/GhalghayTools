package com.example.someapp.model;

public class ContextWarning {

    private String bigram;
    private int position;
    private double score;

    public ContextWarning(String bigram, int position, double score) {
        this.bigram = bigram;
        this.position = position;
        this.score = score;
    }

    public String getBigram() { return bigram; }
    public int getPosition() { return position; }
    public double getScore() { return score; }
}
