package com.acmecorp.payments;

import com.acmecorp.internal.validation.RiskGate;
import com.acmecorp.internal.ledger.LedgerWriter;
import java.math.BigDecimal;

public class PaymentService {

    private final RiskGate riskGate;
    private final LedgerWriter ledgerWriter;

    public PaymentService(RiskGate riskGate, LedgerWriter ledgerWriter) {
        this.riskGate = riskGate;
        this.ledgerWriter = ledgerWriter;
    }

    public boolean processPayment(String accountId, BigDecimal amount) {
        if (!riskGate.screenTransaction(accountId, amount)) {
            return false;
        }
        ledgerWriter.recordDebit(accountId, amount);
        return true;
    }

    public boolean refund(String accountId, BigDecimal amount) {
        ledgerWriter.recordCredit(accountId, amount);
        return true;
    }
}
