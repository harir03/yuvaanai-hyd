// =============================================================================
// Intelli-Credit — useWebSocket Hook
// Manages WebSocket connections with auto-reconnect and exponential backoff.
// One connection per session, shared across components.
// =============================================================================

"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface UseWebSocketOptions {
    /** WebSocket URL to connect to */
    url: string;
    /** Auto-reconnect on disconnect (default: true) */
    autoReconnect?: boolean;
    /** Max reconnect attempts (default: 10) */
    maxRetries?: number;
    /** Base delay for exponential backoff in ms (default: 1000) */
    baseDelay?: number;
    /** Called when a message is received */
    onMessage?: (data: unknown) => void;
    /** Called when connection opens */
    onOpen?: () => void;
    /** Called when connection closes */
    onClose?: () => void;
    /** Called on error */
    onError?: (error: Event) => void;
}

interface UseWebSocketReturn {
    /** Whether the WebSocket is currently connected */
    isConnected: boolean;
    /** Send a message through the WebSocket */
    send: (data: string | object) => void;
    /** Manually reconnect */
    reconnect: () => void;
    /** Manually disconnect */
    disconnect: () => void;
    /** Current retry count */
    retryCount: number;
}

export function useWebSocket({
    url,
    autoReconnect = true,
    maxRetries = 10,
    baseDelay = 1000,
    onMessage,
    onOpen,
    onClose,
    onError,
}: UseWebSocketOptions): UseWebSocketReturn {
    const [isConnected, setIsConnected] = useState(false);
    const [retryCount, setRetryCount] = useState(0);
    const wsRef = useRef<WebSocket | null>(null);
    const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const mountedRef = useRef(true);

    // Store callbacks in refs so effect doesn't re-run on callback changes
    const onMessageRef = useRef(onMessage);
    const onOpenRef = useRef(onOpen);
    const onCloseRef = useRef(onClose);
    const onErrorRef = useRef(onError);
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;

    const connect = useCallback(() => {
        if (!url || wsRef.current?.readyState === WebSocket.OPEN) return;

        // Clean up existing connection
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }

        const ws = new WebSocket(url);

        ws.onopen = () => {
            if (!mountedRef.current) return;
            setIsConnected(true);
            setRetryCount(0);
            onOpenRef.current?.();
        };

        ws.onmessage = (event) => {
            if (!mountedRef.current) return;
            try {
                const data = JSON.parse(event.data);
                onMessageRef.current?.(data);
            } catch {
                onMessageRef.current?.(event.data);
            }
        };

        ws.onclose = () => {
            if (!mountedRef.current) return;
            setIsConnected(false);
            onCloseRef.current?.();

            // Auto-reconnect with exponential backoff
            if (autoReconnect && retryCount < maxRetries) {
                const delay = Math.min(baseDelay * Math.pow(2, retryCount), 30000);
                retryTimeoutRef.current = setTimeout(() => {
                    if (mountedRef.current) {
                        setRetryCount((prev) => prev + 1);
                        connect();
                    }
                }, delay);
            }
        };

        ws.onerror = (error) => {
            if (!mountedRef.current) return;
            onErrorRef.current?.(error);
        };

        wsRef.current = ws;
    }, [url, autoReconnect, maxRetries, baseDelay, retryCount]);

    const disconnect = useCallback(() => {
        if (retryTimeoutRef.current) {
            clearTimeout(retryTimeoutRef.current);
            retryTimeoutRef.current = null;
        }
        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }
        setIsConnected(false);
        setRetryCount(0);
    }, []);

    const reconnect = useCallback(() => {
        disconnect();
        setRetryCount(0);
        // Small delay before reconnecting
        setTimeout(connect, 100);
    }, [connect, disconnect]);

    const send = useCallback((data: string | object) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            const payload = typeof data === "string" ? data : JSON.stringify(data);
            wsRef.current.send(payload);
        }
    }, []);

    // Connect on mount, disconnect on unmount
    useEffect(() => {
        mountedRef.current = true;
        if (url) connect();

        return () => {
            mountedRef.current = false;
            if (retryTimeoutRef.current) {
                clearTimeout(retryTimeoutRef.current);
            }
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [url]); // eslint-disable-line react-hooks/exhaustive-deps

    return { isConnected, send, reconnect, disconnect, retryCount };
}
