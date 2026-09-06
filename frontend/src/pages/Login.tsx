import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useLogin } from "@/lib/queries";
import { apiErrorMessage } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      await login.mutateAsync({ email, password });
      navigate(from, { replace: true });
    } catch (e) {
      setErr(apiErrorMessage(e));
    }
  }

  return (
    <div className="max-w-md mx-auto px-6 py-10">
      <div className="glass p-8">
        <h1 className="text-2xl font-bold">Sign in</h1>
        <p className="text-muted text-sm mt-1">
          Your friendly health assistant is ready when you are.
        </p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <label className="block">
            <span className="text-sm">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full mt-1"
              autoComplete="email"
            />
          </label>
          <label className="block">
            <span className="text-sm">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full mt-1"
              autoComplete="current-password"
            />
          </label>

          {err && <div className="text-red-700 text-sm">{err}</div>}

          <button
            type="submit"
            disabled={login.isPending}
            className="btn-primary w-full disabled:opacity-50"
          >
            {login.isPending ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="mt-6 text-sm text-muted text-center">
          New here?{" "}
          <Link to="/register" className="text-primary hover:underline">
            Create an account
          </Link>
        </div>

        <div className="mt-6 flex items-center gap-3">
          <span className="flex-1 h-px bg-border/60" />
          <span className="text-xs text-muted">or</span>
          <span className="flex-1 h-px bg-border/60" />
        </div>

        <a href="/auth/google/authorize" className="mt-4 btn-ghost w-full justify-center">
          <svg viewBox="0 0 24 24" className="w-4 h-4" aria-hidden="true">
            <path
              fill="#EA4335"
              d="M12 10.2v3.9h5.5c-.2 1.4-1.7 4.1-5.5 4.1-3.3 0-6-2.7-6-6.1s2.7-6.1 6-6.1c1.9 0 3.2.8 3.9 1.5l2.7-2.6C16.9 3.2 14.7 2 12 2 6.9 2 2.8 6.1 2.8 12s4.1 10 9.2 10c5.3 0 8.8-3.7 8.8-8.9 0-.6-.1-1-.1-1.9H12z"
            />
          </svg>
          Continue with Google
        </a>
        <div className="mt-2 text-xs text-muted text-center opacity-70">
          Requires <code>GOOGLE_OAUTH_CLIENT_ID/SECRET</code> in <code>backend/.env</code>.
        </div>
      </div>
    </div>
  );
}
