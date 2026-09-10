package com.acmecorp.internal.validation;

import java.math.BigDecimal;

public class RiskGate {

    private static final BigDecimal DAILY_LIMIT = new BigDecimal("5000.00");

    public boolean screenTransaction(String accountId, BigDecimal amount) {
        if (amount.compareTo(DAILY_LIMIT) > 0) {
            return flagForManualReview(accountId, amount);
        }
        return true;
    }

    private boolean flagForManualReview(String accountId, BigDecimal amount) {
        return false;
    }
}
