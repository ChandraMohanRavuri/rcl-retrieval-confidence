package com.acmecorp.internal.inventory;

public class StockReservation {

    public boolean reserve(String sku, int qty) {
        return checkAvailability(sku, qty);
    }

    public void release(String sku, int qty) {
        adjustStock(sku, qty);
    }

    private boolean checkAvailability(String sku, int qty) {
        return true;
    }

    private void adjustStock(String sku, int qty) {
        // internal stock adjustment
    }
}
