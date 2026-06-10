import { useEffect, useRef, useCallback, useState } from 'react';
import Constants from 'expo-constants';
import type { Bill, Payment } from '../types';

const WS_URL = (Constants.expoConfig?.extra?.apiUrl as string ?? 'http://localhost:8000')
  .replace(/^http/, 'ws');

type WSMessage =
  | { type: 'init'; data: Bill }
  | { type: 'payment_confirmed'; payment: Payment; participant_name: string }
  | { type: 'ping' };

interface Options {
  billId: string;
  onInit: (bill: Bill) => void;
  onPaymentConfirmed: (payment: Payment, name: string) => void;
}

export function useDashboardWS({ billId, onInit, onPaymentConfirmed }: Options) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (!mounted.current) return;
    if (ws.current) {
      ws.current.onclose = null;
      ws.current.close();
    }

    const socket = new WebSocket(`${WS_URL}/ws/dashboard/${billId}`);
    ws.current = socket;

    socket.onopen = () => {
      if (!mounted.current) return;
      setConnected(true);
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    socket.onmessage = (event) => {
      if (!mounted.current) return;
      try {
        const msg: WSMessage = JSON.parse(event.data);
        if (msg.type === 'init') onInit(msg.data);
        else if (msg.type === 'payment_confirmed') onPaymentConfirmed(msg.payment, msg.participant_name);
      } catch {}
    };

    socket.onclose = () => {
      if (!mounted.current) return;
      setConnected(false);
      // Reconnect after 3s
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    socket.onerror = () => {
      socket.close();
    };
  }, [billId, onInit, onPaymentConfirmed]);

  useEffect(() => {
    mounted.current = true;
    connect();
    return () => {
      mounted.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (ws.current) {
        ws.current.onclose = null;
        ws.current.close();
      }
    };
  }, [connect]);

  return { connected };
}
