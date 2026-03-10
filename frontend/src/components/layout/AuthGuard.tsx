"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";

/** 
 * Wraps the app shell. On non-login pages, redirects to /login if not authenticated.
 * On /login, renders children directly (no sidebar/header).
 */
export function AuthGuard({ children }: { children: ReactNode }) {
    const { user, isLoading } = useAuth();
    const pathname = usePathname();
    const router = useRouter();
    const isLoginPage = pathname === "/login";

    useEffect(() => {
        if (!isLoading && !user && !isLoginPage) {
            router.replace("/login");
        }
    }, [user, isLoading, isLoginPage, router]);

    // While checking auth, show a simple loading state
    if (isLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-slate-50">
                <div className="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin" />
            </div>
        );
    }

    // Login page — render without sidebar/header wrapper
    if (isLoginPage) {
        return <>{children}</>;
    }

    // Not authenticated — show nothing while redirect fires
    if (!user) {
        return null;
    }

    // Authenticated — render full app shell
    return <>{children}</>;
}
