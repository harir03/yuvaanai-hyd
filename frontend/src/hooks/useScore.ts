// =============================================================================
// Intelli-Credit — useScore Hook
// Fetches and manages score data with mock data fallback.
// =============================================================================

"use client";

import { useState, useEffect, useCallback } from "react";
import { getScoreResult } from "@/lib/api";
import {
    mockAssessment,
    mockScoreModules,
    type ScoreModule,
} from "@/lib/mockData";

interface UseScoreOptions {
    /** Session ID for the assessment */
    sessionId: string | null;
}

interface UseScoreReturn {
    /** Final credit score (0-850) */
    score: number;
    /** Score band label */
    scoreBand: string;
    /** Assessment outcome */
    outcome: string;
    /** Score modules with per-metric breakdown */
    modules: ScoreModule[];
    /** Whether data is loading */
    loading: boolean;
    /** Error message if fetch failed */
    error: string | null;
    /** Refresh score data */
    refresh: () => Promise<void>;
}

export function useScore({ sessionId }: UseScoreOptions): UseScoreReturn {
    const [score, setScore] = useState(mockAssessment.score);
    const [scoreBand, setScoreBand] = useState(mockAssessment.scoreBand);
    const [outcome, setOutcome] = useState(mockAssessment.outcome);
    const [modules, setModules] = useState<ScoreModule[]>(mockScoreModules);
    const [loading, setLoading] = useState(!!sessionId);
    const [error, setError] = useState<string | null>(null);

    const fetchScore = useCallback(async () => {
        if (!sessionId) return;
        setLoading(true);
        setError(null);

        try {
            const result = await getScoreResult(sessionId);
            setScore(result.score);
            setScoreBand(result.scoreBand);
            setOutcome(result.outcome);
            setModules(result.modules);
        } catch (err) {
            // Keep mock data on error
            setError(err instanceof Error ? err.message : "Failed to load score");
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        fetchScore();
    }, [fetchScore]);

    return {
        score,
        scoreBand,
        outcome,
        modules,
        loading,
        error,
        refresh: fetchScore,
    };
}
