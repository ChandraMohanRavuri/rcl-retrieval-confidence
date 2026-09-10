package com.acmecorp.notifications;

public class NotificationService {

    public void sendEmail(String to, String subject, String body) {
        dispatch(to, subject, body);
    }

    private void dispatch(String to, String subject, String body) {
        // generic dispatch, not internal-specific
    }
}
