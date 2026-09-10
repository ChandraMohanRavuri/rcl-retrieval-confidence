package com.acmecorp.orders;

import com.acmecorp.internal.inventory.StockReservation;
import com.acmecorp.payments.PaymentService;
import java.math.BigDecimal;

public class OrderService {

    private final StockReservation stockReservation;
    private final PaymentService paymentService;

    public OrderService(StockReservation stockReservation, PaymentService paymentService) {
        this.stockReservation = stockReservation;
        this.paymentService = paymentService;
    }

    public boolean placeOrder(String sku, int qty, String accountId, BigDecimal price) {
        if (!stockReservation.reserve(sku, qty)) {
            return false;
        }
        boolean paid = paymentService.processPayment(accountId, price);
        if (!paid) {
            stockReservation.release(sku, qty);
        }
        return paid;
    }
}
