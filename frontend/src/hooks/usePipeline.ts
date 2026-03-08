// =============================================================================
// Intelli-Credit — usePipeline Hook
// Tracks pipeline progress by polling the API with mock data fallback.
// =============================================================================

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getPipelineStatus } from "@/lib/api";
import {
    mockPipeline,
    mockWorkers,
    type PipelineStage,
    type WorkerStatus,
} from "@/lib/mockData";

interface UsePipelineOptions {
    /** Session ID to track */
    sessionId: string | null;
    /** Polling interval in ms (default: 3000) */
    pollInterval?: number;
}

interface UsePipelineReturn {
    /** Pipeline stage statuses */
    stages: PipelineStage[];
    /** Worker statuses */
    workers: WorkerStatus[];
    /** Whether the pipeline is complete */
    isComplete: boolean;
    /** Whether any stage has failed */
    hasFailed: boolean;
    /** Current active stage name */
    currentStage: string | null;
    /** Overall progress percentage (0-100) */
    progress: number;
}

export function usePipeline({
    sessionId,
    pollInterval = 3000,
}: UsePipelineOptions): UsePipelineReturn {
    const [stages, setStages] = useState<PipelineStage[]>(mockPipeline);
    const [workers, setWorkers] = useState<WorkerStatus[]>(mockWorkers);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const poll = useCallback(async () => {
        if (!sessionId) return;
        try {
            const status = await getPipelineStatus(sessionId);
            setStages(status.stages);
            if (status.workers) setWorkers(status.workers);
        } catch {
            // Keep current/mock data on error
        }
    }, [sessionId]);

    useEffect(() => {
        if (!sessionId) return;

        poll(); // Initial fetch
        intervalRef.current = setInterval(poll, pollInterval);

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [sessionId, pollInterval, poll]);

    const isComplete = stages.every(
        (s) => s.status === "completed" || s.status === "skipped",
    );

    const hasFailed = stages.some((s) => s.status === "failed");

    const currentStage =
        stages.find((s) => s.status === "in_progress")?.name ?? null;

    const completed = stages.filter(
        (s) => s.status === "completed" || s.status === "skipped",
    ).length;
    const progress = stages.length > 0 ? Math.round((completed / stages.length) * 100) : 0;

    return { stages, workers, isComplete, hasFailed, currentStage, progress };
}
