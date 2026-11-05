import { useCallback, useEffect, useRef, useState } from 'react';
import { WS_URL } from '../lib/config';
import { supabase } from '../lib/supabase';
import type { Bill, Payment } from '../types';

type WSMessage =
  | { type: 'init'; data: Bill }
  | { type: 'payment_confirmed'; payment: Payment; participant_name: string }
  | { type: 'ping' };

interface Options {
  billId: string;
  onInit: (bill: Bill) => void;
  onPaymentConfirmed: (payment: Payment, name: string) => void;
}

/** The server closes with this code when the token is missing/invalid or not the bill's owner. */
const CLOSE_UNAUTHORISED = 4401;
const RECONNECT_MS = 3000;

export function useDashboardWS({ billId, onInit, onPaymentConfirmed }: Options) {
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(() => {
    if (!mounted.current || !billId) return;
    if (ws.current) {
      ws.current.onclose = null;
      ws.current.close();
    }

    const socket = new WebSocket(`${WS_URL}/ws/dashboard/${billId}`);
    ws.current = socket;

    socket.onopen = async () => {
      if (!mounted.current) return;
      // Authenticate with the first message (not the URL, which ends up in access logs).
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token) {
        socket.close();
        return;
      }
      socket.send(JSON.stringify({ type: 'auth', token }));
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
      } catch {
        // Ignore malformed frames.
      }
    };

    socket.onclose = (event) => {
      if (!mounted.current) return;
      setConnected(false);
      // A rejected login will be rejected again: don't hammer the server.
      if (event.code === CLOSE_UNAUTHORISED) return;
      reconnectTimer.current = setTimeout(connect, RECONNECT_MS);
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
