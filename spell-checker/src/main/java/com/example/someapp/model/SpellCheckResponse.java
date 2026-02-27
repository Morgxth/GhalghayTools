package com.example.someapp.model;

import java.util.List;

public class SpellCheckResponse {

    private boolean hasErrors;
    private List<WordCorrection> corrections;
    private List<ContextWarning> contextWarnings;

    public SpellCheckResponse(boolean hasErrors, List<WordCorrection> corrections, List<ContextWarning> contextWarnings) {
        this.hasErrors = hasErrors;
        this.corrections = corrections;
        this.contextWarnings = contextWarnings;
    }

    public boolean isHasErrors() { return hasErrors; }
    public List<WordCorrection> getCorrections() { return corrections; }
    public List<ContextWarning> getContextWarnings() { return contextWarnings; }
}
