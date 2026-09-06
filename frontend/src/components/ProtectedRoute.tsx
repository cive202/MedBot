import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/lib/auth";

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status, refresh } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (status === "idle") void refresh();
  }, [status, refresh]);

  if (status === "idle" || status === "loading") {
    return (
      <div className="min-h-[40vh] flex items-center justify-center text-muted">
        Loading…
      </div>
    );
  }
  if (status === "unauthenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
