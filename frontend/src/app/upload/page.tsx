"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
    Upload,
    FileText,
    CheckCircle2,
    AlertCircle,
    Building2,
    CreditCard,
    User,
    MapPin,
    ArrowRight,
    X,
    File,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { mockDocuments, type DocumentUpload } from "@/lib/mockData";
import { uploadDocuments } from "@/lib/api";

const REQUIRED_DOCUMENTS = [
    { type: "Annual Report", label: "Annual Report (3 years)", icon: FileText, required: true },
    { type: "Bank Statement", label: "Bank Statement (12 months)", icon: FileText, required: true },
    { type: "GST Returns", label: "GST Returns (GSTR-3B & 2A)", icon: FileText, required: true },
    { type: "ITR", label: "Income Tax Returns", icon: FileText, required: true },
    { type: "Legal Notice", label: "Legal Notices (if any)", icon: FileText, required: false },
    { type: "Board Minutes", label: "Board Minutes", icon: FileText, required: true },
    { type: "Shareholding", label: "Shareholding Pattern", icon: FileText, required: true },
    { type: "Rating Report", label: "Credit Rating Report", icon: FileText, required: false },
];

export default function UploadPage() {
    const router = useRouter();
    const [companyName, setCompanyName] = useState("");
    const [cin, setCin] = useState("");
    const [loanAmount, setLoanAmount] = useState("");
    const [loanType, setLoanType] = useState("Working Capital");
    const [sector, setSector] = useState("");
    const [promoter, setPromoter] = useState("");
    const [uploadedFiles, setUploadedFiles] = useState<Record<string, File | null>>({});
    const [isDragging, setIsDragging] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);

    const handleDrop = useCallback((docType: string, e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(null);
        const file = e.dataTransfer.files[0];
        if (file) {
            setUploadedFiles((prev) => ({ ...prev, [docType]: file }));
        }
    }, []);

    const handleFileInput = useCallback((docType: string, e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setUploadedFiles((prev) => ({ ...prev, [docType]: file }));
        }
    }, []);

    const removeFile = (docType: string) => {
        setUploadedFiles((prev) => {
            const updated = { ...prev };
            delete updated[docType];
            return updated;
        });
    };

    const totalRequired = REQUIRED_DOCUMENTS.filter((d) => d.required).length;
    const requiredUploaded = REQUIRED_DOCUMENTS.filter((d) => d.required && uploadedFiles[d.type]).length;
    const canSubmit = companyName && cin && loanAmount && requiredUploaded >= totalRequired;

    const handleStartAssessment = async () => {
        setIsSubmitting(true);
        setSubmitError(null);
        try {
            const files: Record<string, File> = {};
            for (const [docType, file] of Object.entries(uploadedFiles)) {
                if (file) files[docType] = file;
            }
            const result = await uploadDocuments({
                companyName,
                cin,
                loanAmount,
                loanType,
                sector,
                promoter,
                files,
            });
            router.push(`/processing?session=${encodeURIComponent(result.sessionId)}`);
        } catch (err) {
            setSubmitError(err instanceof Error ? err.message : "Upload failed. Check if backend is running.");
            setIsSubmitting(false);
        }
    };

    return (
        <div className="p-6 space-y-6 max-w-[1600px] mx-auto min-h-screen">
            {/* Page Header */}
            <div className="flex items-center gap-3">
                <div className="p-2.5 bg-teal-500/10 rounded-xl">
                    <Upload className="w-6 h-6 text-teal-600" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-slate-800">New Credit Assessment</h1>
                    <p className="text-sm text-slate-500">Upload corporate loan documents for AI-powered credit appraisal</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Company Information Form */}
                <div className="lg:col-span-1 space-y-4">
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
                        <div className="flex items-center gap-2 mb-5">
                            <Building2 className="w-5 h-5 text-slate-400" />
                            <h2 className="text-base font-bold text-slate-900">Company Information</h2>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Company Name *</label>
                                <input
                                    type="text"
                                    value={companyName}
                                    onChange={(e) => setCompanyName(e.target.value)}
                                    placeholder="e.g., XYZ Steel Private Limited"
                                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">CIN Number *</label>
                                <input
                                    type="text"
                                    value={cin}
                                    onChange={(e) => setCin(e.target.value)}
                                    placeholder="e.g., U27100MH2005PTC123456"
                                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-medium font-mono focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Loan Amount *</label>
                                    <input
                                        type="text"
                                        value={loanAmount}
                                        onChange={(e) => setLoanAmount(e.target.value)}
                                        placeholder="₹50,00,00,000"
                                        className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Loan Type</label>
                                    <select
                                        value={loanType}
                                        onChange={(e) => setLoanType(e.target.value)}
                                        className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all"
                                    >
                                        <option>Working Capital</option>
                                        <option>Term Loan</option>
                                        <option>Letter of Credit</option>
                                        <option>Bank Guarantee</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Sector</label>
                                <input
                                    type="text"
                                    value={sector}
                                    onChange={(e) => setSector(e.target.value)}
                                    placeholder="e.g., Steel Manufacturing"
                                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400"
                                />
                            </div>

                            <div>
                                <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-1.5">Promoter Name</label>
                                <input
                                    type="text"
                                    value={promoter}
                                    onChange={(e) => setPromoter(e.target.value)}
                                    placeholder="e.g., Rajesh Kumar Agarwal"
                                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm font-medium focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 transition-all placeholder:text-slate-400"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Upload Progress Summary */}
                    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6">
                        <h3 className="text-sm font-bold text-slate-800 mb-3">Upload Progress</h3>
                        <div className="flex items-center gap-3 mb-3">
                            <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div
                                    className="h-full bg-teal-400 rounded-full transition-all duration-500"
                                    style={{ width: `${(Object.keys(uploadedFiles).length / REQUIRED_DOCUMENTS.length) * 100}%` }}
                                />
                            </div>
                            <span className="text-xs font-bold text-slate-500">
                                {Object.keys(uploadedFiles).length}/{REQUIRED_DOCUMENTS.length}
                            </span>
                        </div>
                        <p className="text-[11px] text-slate-400">
                            {requiredUploaded < totalRequired
                                ? `${totalRequired - requiredUploaded} mandatory document(s) remaining`
                                : "✅ All mandatory documents uploaded"}
                        </p>

                        {submitError && (
                            <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-600">
                                {submitError}
                            </div>
                        )}

                        <button
                            onClick={handleStartAssessment}
                            disabled={!canSubmit || isSubmitting}
                            className={cn(
                                "w-full mt-4 flex items-center justify-center gap-2 px-6 py-3 rounded-lg font-bold text-sm transition-all uppercase tracking-wide",
                                canSubmit && !isSubmitting
                                    ? "bg-teal-500 hover:bg-teal-600 text-white shadow-lg shadow-teal-500/20 active:scale-95"
                                    : "bg-slate-100 text-slate-400 cursor-not-allowed"
                            )}
                        >
                            {isSubmitting ? "Uploading..." : "Start Assessment"} <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Document Upload Grid */}
                <div className="lg:col-span-2">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {REQUIRED_DOCUMENTS.map((doc) => {
                            const uploaded = uploadedFiles[doc.type];
                            return (
                                <div
                                    key={doc.type}
                                    onDragOver={(e) => { e.preventDefault(); setIsDragging(doc.type); }}
                                    onDragLeave={() => setIsDragging(null)}
                                    onDrop={(e) => handleDrop(doc.type, e)}
                                    className={cn(
                                        "bg-white rounded-xl border-2 border-dashed p-5 transition-all relative group",
                                        isDragging === doc.type
                                            ? "border-teal-400 bg-teal-50/50 scale-[1.02]"
                                            : uploaded
                                                ? "border-emerald-200 bg-emerald-50/30"
                                                : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50"
                                    )}
                                >
                                    <div className="flex items-start justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <div className={cn(
                                                "w-8 h-8 rounded-lg flex items-center justify-center",
                                                uploaded ? "bg-emerald-100" : "bg-slate-100"
                                            )}>
                                                {uploaded ? (
                                                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                                                ) : (
                                                    <doc.icon className="w-4 h-4 text-slate-400" />
                                                )}
                                            </div>
                                            <div>
                                                <p className="text-sm font-bold text-slate-800">{doc.label}</p>
                                                <p className="text-[10px] text-slate-400 uppercase tracking-wider">
                                                    {doc.required ? "Mandatory" : "Optional"}
                                                </p>
                                            </div>
                                        </div>
                                        {doc.required && !uploaded && (
                                            <span className="text-[9px] font-bold text-red-400 bg-red-50 px-1.5 py-0.5 rounded uppercase">Required</span>
                                        )}
                                    </div>

                                    {uploaded ? (
                                        <div className="flex items-center justify-between bg-white rounded-lg border border-slate-100 px-3 py-2">
                                            <div className="flex items-center gap-2 min-w-0">
                                                <File className="w-4 h-4 text-teal-500 shrink-0" />
                                                <span className="text-xs font-medium text-slate-700 truncate">{uploaded.name}</span>
                                                <span className="text-[10px] text-slate-400 shrink-0">
                                                    {(uploaded.size / 1024 / 1024).toFixed(1)} MB
                                                </span>
                                            </div>
                                            <button
                                                onClick={() => removeFile(doc.type)}
                                                className="p-1 rounded-full hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors"
                                            >
                                                <X className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    ) : (
                                        <label className="flex flex-col items-center gap-1 cursor-pointer py-2">
                                            <Upload className="w-5 h-5 text-slate-300" />
                                            <span className="text-[11px] text-slate-400 font-medium">
                                                Drop file or <span className="text-teal-500 font-bold">browse</span>
                                            </span>
                                            <span className="text-[9px] text-slate-300">PDF, XLSX, CSV — Max 50MB</span>
                                            <input
                                                type="file"
                                                accept=".pdf,.xlsx,.xls,.csv"
                                                className="hidden"
                                                onChange={(e) => handleFileInput(doc.type, e)}
                                            />
                                        </label>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
}
