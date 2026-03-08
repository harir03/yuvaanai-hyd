// =============================================================================
// Intelli-Credit — useAssessment Hook
// Manages assessment state: company info, score, CAM, pipeline stages.
// Fetches from the API with mock data fallback.
// =============================================================================

"use client";

import { useState, useEffect, useCallback } from "react";
import {
    getAssessment,
    getScoreResult,
    type ScoreResult,
} from "@/lib/api";
import {
    mockAssessment,
    mockCompany,
    mockScoreModules,
    mockCAM,
    type CompanyInfo,
    type ScoreModule,
    type CAMSection,
} from "@/lib/mockData";

interface UseAssessmentOptions {
    /** Session ID for the assessment */
    sessionId: string | null;
}

interface UseAssessmentReturn {
    /** Company information */
    company: CompanyInfo;
    /** Final credit score (0-850) */
    score: number;
    /** Score band label */
    scoreBand: string;
    /** Assessment outcome */
    outcome: string;
    /** Score modules with breakdown */
    modules: ScoreModule[];
    /** CAM sections */
    camSections: CAMSection[];
    /** Whether data is loading */
    loading: boolean;
    /** Error message if fetch failed */
    error: string | null;
    /** Refresh assessment data */
    refresh: () => Promise<void>;
}

export function useAssessment({
    sessionId,
}: UseAssessmentOptions): UseAssessmentReturn {
    const [company, setCompany] = useState<CompanyInfo>(mockCompany);
    const [score, setScore] = useState(mockAssessment.score);
    const [scoreBand, setScoreBand] = useState(mockAssessment.scoreBand);
    const [outcome, setOutcome] = useState(mockAssessment.outcome);
    const [modules, setModules] = useState<ScoreModule[]>(mockScoreModules);
    const [camSections, setCamSections] = useState<CAMSection[]>(mockCAM);
    const [loading, setLoading] = useState(!!sessionId);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        if (!sessionId) return;
        setLoading(true);
        setError(null);

        try {
            const [assessment, scoreResult] = await Promise.all([
                getAssessment(sessionId),
                getScoreResult(sessionId),
            ]);

            setCompany(assessment.company);
            setScore(scoreResult.score);
            setScoreBand(scoreResult.scoreBand);
            setOutcome(scoreResult.outcome);
            setModules(scoreResult.modules);
            if (scoreResult.camSections) {
                setCamSections(scoreResult.camSections);
            }
        } catch (err) {
            // Fall back to mock data
            setError(err instanceof Error ? err.message : "Failed to load assessment");
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    return {
        company,
        score,
        scoreBand,
        outcome,
        modules,
        camSections,
        loading,
        error,
        refresh: fetchData,
    };
}
