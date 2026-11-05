import { useRouter } from 'expo-router';
import * as Notifications from 'expo-notifications';
import { useEffect, useRef } from 'react';
import { registerPushToken } from '../lib/api';
import {
  addNotificationListener,
  addResponseListener,
  registerForPushNotifications,
} from '../lib/notifications';

/**
 * Registers this device for the signed-in organiser's 'X paid' pushes and
 * deep-links a tapped notification to its bill.
 *
 * `userId` is undefined while signed out, so nothing is registered. (Before, the
 * hook was called with no id and the token was never sent: organisers never got
 * pushes, because the server also looked tokens up by a column nothing wrote.)
 */
export function usePushNotifications(userId?: string) {
  const router = useRouter();
  const notifListener = useRef<Notifications.EventSubscription | null>(null);
  const responseListener = useRef<Notifications.EventSubscription | null>(null);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    registerForPushNotifications().then((token) => {
      if (!token || cancelled) return;
      registerPushToken(token).catch((e) => console.warn('Failed to register push token:', e));
    });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  useEffect(() => {
    notifListener.current = addNotificationListener((notification) => {
      // Foreground: no-op, the dashboard WebSocket already updates live.
      console.log('Push received (foreground):', notification.request.identifier);
    });

    responseListener.current = addResponseListener((response) => {
      const data = response.notification.request.content.data as Record<string, string>;
      if (data?.billId) {
        router.push(`/bill/${data.billId}`);
      }
    });

    return () => {
      notifListener.current?.remove();
      responseListener.current?.remove();
    };
  }, [router]);
}
