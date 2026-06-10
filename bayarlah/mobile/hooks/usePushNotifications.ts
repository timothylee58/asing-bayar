import { useEffect, useRef, useState } from 'react';
import * as Notifications from 'expo-notifications';
import Constants from 'expo-constants';
import {
  registerForPushNotifications,
  sendPushTokenToServer,
  addNotificationListener,
  addResponseListener,
} from '../lib/notifications';
import { useRouter } from 'expo-router';

const API_URL = (Constants.expoConfig?.extra?.apiUrl as string) ?? 'http://localhost:8000';

export function usePushNotifications(participantId?: string) {
  const [pushToken, setPushToken] = useState<string | null>(null);
  const notifListener = useRef<Notifications.EventSubscription | null>(null);
  const responseListener = useRef<Notifications.EventSubscription | null>(null);
  const router = useRouter();

  useEffect(() => {
    registerForPushNotifications().then((token) => {
      if (!token) return;
      setPushToken(token);
      if (participantId) {
        sendPushTokenToServer(token, participantId, API_URL);
      }
    });

    notifListener.current = addNotificationListener((notification) => {
      // Notification received while app is foregrounded — no-op, WS handles live updates
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
  }, [participantId]);

  return { pushToken };
}
