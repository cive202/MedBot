import { useEffect } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Profile from "./pages/Profile";
import Chat from "./pages/Chat";
import Analyze from "./pages/Analyze";
import Specialists from "./pages/Specialists";
import ProtectedRoute from "./components/ProtectedRoute";
import DisclaimerBanner from "./components/DisclaimerBanner";
import { useAuth } from "./lib/auth";

/**
 * Routing:
 *  - `/`          landing page for visitors, chat for signed-in users
 *  - `/chat`      open to everyone; guests just don't get saved history
 *  - `/analyze`   open to everyone (uploads are never stored)
 *  - `/specialists` open to everyone (guests supply coordinates directly)
 *  - `/profile`   requires an account — there is no profile without one
 */
export default function App() {
  const { user, status, refresh, logout } = useAuth();

  useEffect(() => {
    if (status === "idle") void refresh();
  }, [status, refresh]);

  const location = useLocation();
  const authed = status === "authenticated";
  const resolving = status === "idle" || status === "loading";

  // The landing page ships its own header and footer, and the auth pages are
  // deliberately bare, so the app chrome stays out of the way on all three.
  const bareRoutes = ["/login", "/register"];
  const isBare = bareRoutes.includes(location.pathname);
  const isLanding = location.pathname === "/" && !authed && !resolving;
  const showChrome = !isBare && !isLanding && !resolving;

  return (
    <div className="min-h-screen flex flex-col">
      {showChrome && <DisclaimerBanner />}

      {showChrome && (
        <header className="px-6 py-3 flex items-center justify-between border-b border-border/60 bg-white/70 backdrop-blur-sm">
          <Link to="/" className="font-semibold tracking-tight text-lg">
            <span className="text-primary">Med</span>Assist
          </Link>
          <nav className="text-sm flex items-center gap-4">
            <Link to="/chat" className="hover:text-primary">Chat</Link>
            <Link to="/analyze" className="hover:text-primary">Analyze</Link>
            <Link to="/specialists" className="hover:text-primary">Specialists</Link>
            {authed ? (
              <>
                <Link to="/profile" className="hover:text-primary">Profile</Link>
                <span className="text-muted hidden sm:inline">{user?.email}</span>
                <button className="btn-ghost" onClick={() => logout()}>Logout</button>
              </>
            ) : (
              <>
                <Link to="/login" className="hover:text-primary">Sign in</Link>
                <Link to="/register" className="btn btn-primary py-1.5 px-3">
                  Create account
                </Link>
              </>
            )}
          </nav>
        </header>
      )}

      <main className="flex-1 flex flex-col">
        <Routes>
          <Route path="/" element={<RootGate />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/analyze" element={<Analyze />} />
          <Route path="/specialists" element={<Specialists />} />
          <Route path="/login" element={<UnauthedOnly><Login /></UnauthedOnly>} />
          <Route path="/register" element={<UnauthedOnly><Register /></UnauthedOnly>} />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Profile />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

/**
 * Home route: signed-in users land straight in the chat, visitors see the
 * marketing page (whose primary CTA drops them into `/chat` as a guest).
 */
function RootGate() {
  const { status } = useAuth();
  if (status === "idle" || status === "loading") {
    return (
      <div className="min-h-[40vh] flex items-center justify-center text-muted">
        Loading…
      </div>
    );
  }
  return status === "authenticated" ? <Chat /> : <Landing />;
}

/** Already signed in? `/login` and `/register` bounce home. */
function UnauthedOnly({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === "authenticated") return <Navigate to="/" replace />;
  return <>{children}</>;
}
