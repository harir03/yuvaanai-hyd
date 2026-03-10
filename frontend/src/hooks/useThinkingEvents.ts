// =============================================================================
// Intelli-Credit — useThinkingEvents Hook
// Handles the thinking event stream from WebSocket with filtering.
// Connects to the thinking WS endpoint and manages event state.
// =============================================================================

"use client";

import { useState, useCallback, useMemo } from "react";
import { useWebSocket } from "./useWebSocket";
import { type ThinkingEvent, mockThinkingEvents } from "@/lib/mockData";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");

interface UseThinkingEventsOptions {
    /** Session ID to connect to */
    sessionId: string | null;
    /** Whether to use mock data when no session (default: true) */
    useMock?: boolean;
}

interface UseThinkingEventsReturn {
    /** All received thinking events */
    events: ThinkingEvent[];
    /** Whether the WebSocket is connected */
    isConnected: boolean;
    /** Filter events by agent name */
    filterByAgent: (agent: string | null) => ThinkingEvent[];
    /** Filter events by event type */
    filterByType: (type: string | null) => ThinkingEvent[];
    /** Clear all events */
    clear: () => void;
    /** Reconnect to WebSocket */
    reconnect: () => void;
}

export function useThinkingEvents({
    sessionId,
    useMock = true,
}: UseThinkingEventsOptions): UseThinkingEventsReturn {
    const [events, setEvents] = useState<ThinkingEvent[]>(
        !sessionId && useMock ? mockThinkingEvents : [],
    );

    const handleMessage = useCallback((data: unknown) => {
        const event = data as ThinkingEvent;
        if (event && event.eventType) {
            setEvents((prev) => [...prev, event]);
        }
    }, []);

    const wsUrl = sessionId ? `${WS_BASE}/ws/thinking/${sessionId}` : "";

    const { isConnected, reconnect } = useWebSocket({
        url: wsUrl,
        onMessage: handleMessage,
        autoReconnect: true,
    });

    const filterByAgent = useCallback(
        (agent: string | null) => {
            if (!agent) return events;
            return events.filter(
                (e) => e.agent?.toLowerCase().includes(agent.toLowerCase()),
            );
        },
        [events],
    );

    const filterByType = useCallback(
        (type: string | null) => {
            if (!type) return events;
            return events.filter((e) => e.eventType === type);
        },
        [events],
    );

    const clear = useCallback(() => setEvents([]), []);

    return {
        events,
        isConnected,
        filterByAgent,
        filterByType,
        clear,
        reconnect,
    };
}
