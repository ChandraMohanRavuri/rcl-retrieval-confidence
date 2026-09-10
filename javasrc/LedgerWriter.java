package com.acmecorp.internal.ledger;

import java.math.BigDecimal;

public class LedgerWriter {

    public void recordDebit(String accountId, BigDecimal amount) {
        appendEntry(accountId, amount.negate());
    }

    public void recordCredit(String accountId, BigDecimal amount) {
        appendEntry(accountId, amount);
    }

    private void appendEntry(String accountId, BigDecimal signedAmount) {
        // internal ledger append logic
    }
}
