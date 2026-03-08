// =============================================================================
// Intelli-Credit — useTickets Hook
// Manages ticket state: fetching, resolving, escalating.
// Falls back to mock data when backend is unavailable.
// =============================================================================

"use client";

import { useState, useEffect, useCallback } from "react";
import { getTickets, resolveTicket, escalateTicket } from "@/lib/api";
import { mockTickets, type Ticket } from "@/lib/mockData";

interface UseTicketsOptions {
    /** Session ID for the assessment */
    sessionId: string | null;
}

interface UseTicketsReturn {
    /** All tickets for this assessment */
    tickets: Ticket[];
    /** Currently selected ticket */
    selectedTicket: Ticket | null;
    /** Select a ticket by ID */
    selectTicket: (ticketId: string) => void;
    /** Resolve a ticket with a response */
    resolve: (ticketId: string, response: string, action: string) => Promise<void>;
    /** Escalate a ticket */
    escalate: (ticketId: string, reason: string) => Promise<void>;
    /** Whether a resolve/escalate operation is in progress */
    isProcessing: boolean;
    /** Open tickets count */
    openCount: number;
    /** Resolved tickets count */
    resolvedCount: number;
    /** Error message if operation failed */
    error: string | null;
}

export function useTickets({
    sessionId,
}: UseTicketsOptions): UseTicketsReturn {
    const [tickets, setTickets] = useState<Ticket[]>(mockTickets);
    const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(
        mockTickets[0] ?? null,
    );
    const [isProcessing, setIsProcessing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch tickets from API
    useEffect(() => {
        if (!sessionId) return;

        getTickets(sessionId)
            .then((data) => {
                setTickets(data);
                if (data.length > 0) setSelectedTicket(data[0]);
            })
            .catch(() => {
                // Keep mock data
            });
    }, [sessionId]);

    const selectTicket = useCallback(
        (ticketId: string) => {
            const ticket = tickets.find((t) => t.id === ticketId) ?? null;
            setSelectedTicket(ticket);
        },
        [tickets],
    );

    const resolve = useCallback(
        async (ticketId: string, response: string, action: string) => {
            setIsProcessing(true);
            setError(null);
            try {
                if (sessionId) {
                    await resolveTicket(sessionId, ticketId, response, action);
                }
                // Update local state
                setTickets((prev) =>
                    prev.map((t) =>
                        t.id === ticketId
                            ? { ...t, status: "resolved" as const, resolution: response }
                            : t,
                    ),
                );
            } catch (err) {
                setError(
                    err instanceof Error ? err.message : "Failed to resolve ticket",
                );
            } finally {
                setIsProcessing(false);
            }
        },
        [sessionId],
    );

    const escalate = useCallback(
        async (ticketId: string, reason: string) => {
            setIsProcessing(true);
            setError(null);
            try {
                if (sessionId) {
                    await escalateTicket(sessionId, ticketId, reason);
                }
                setTickets((prev) =>
                    prev.map((t) =>
                        t.id === ticketId
                            ? { ...t, status: "escalated" as const }
                            : t,
                    ),
                );
            } catch (err) {
                setError(
                    err instanceof Error ? err.message : "Failed to escalate ticket",
                );
            } finally {
                setIsProcessing(false);
            }
        },
        [sessionId],
    );

    const openCount = tickets.filter((t) => t.status === "open").length;
    const resolvedCount = tickets.filter((t) => t.status === "resolved").length;

    return {
        tickets,
        selectedTicket,
        selectTicket,
        resolve,
        escalate,
        isProcessing,
        openCount,
        resolvedCount,
        error,
    };
}
