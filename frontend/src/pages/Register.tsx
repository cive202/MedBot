import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Shuffle } from "lucide-react";
import { useRegister } from "@/lib/queries";
import { apiErrorMessage } from "@/lib/api";
import { generateUsername, isValidUsername } from "@/lib/username";
import { BLOOD_GROUPS, type BloodGroup, type History, type Location, type Sex } from "@/types/user";

type Step = 1 | 2 | 3;

// Same bounds as backend schema (1920-01-01 .. 2026-12-31).
const DOB_MIN = "1920-01-01";
const DOB_MAX = "2026-12-31";

export default function Register() {
  const [step, setStep] = useState<Step>(1);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fullName, setFullName] = useState("");
  const [dob, setDob] = useState("");
  const [sex, setSex] = useState<Sex>("prefer_not_to_say");
  const [bloodGroup, setBloodGroup] = useState<BloodGroup>("unknown");
  const [conditions, setConditions] = useState("");
  const [medications, setMedications] = useState("");
  const [allergies, setAllergies] = useState("");
  const [notes, setNotes] = useState("");
  const [loc, setLoc] = useState<Location | null>(null);
  const [latInput, setLatInput] = useState("");
  const [lonInput, setLonInput] = useState("");
  const [geoMsg, setGeoMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const navigate = useNavigate();
  const register = useRegister();

  const usernameValid = username === "" || isValidUsername(username);
  const dobValid = dob === "" || (dob >= DOB_MIN && dob <= DOB_MAX);

  function rollUsername() {
    setUsername(generateUsername());
  }

  function requestLocation() {
    if (!navigator.geolocation) {
      setGeoMsg("Geolocation not supported by this browser.");
      return;
    }
    setGeoMsg("Requesting location…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const next = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        setLoc(next);
        setLatInput(next.lat.toFixed(6));
        setLonInput(next.lon.toFixed(6));
        setGeoMsg(`Got it (${next.lat.toFixed(3)}, ${next.lon.toFixed(3)})`);
      },
      (e) => setGeoMsg(`Skipped: ${e.message}`),
      { timeout: 8000 },
    );
  }

  function resolveLocation(): Location | null {
    if (latInput.trim() === "" && lonInput.trim() === "") return loc;
    const lat = Number(latInput);
    const lon = Number(lonInput);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
    return { lat, lon };
  }

  async function submit() {
    setErr(null);
    if (password !== confirm) {
      setErr("Passwords do not match.");
      return;
    }
    if (!usernameValid) {
      setErr("Username must be 3-30 chars, start with a letter, and use only letters, digits, '_' or '-'.");
      return;
    }
    if (!dobValid) {
      setErr(`Date of birth must be between ${DOB_MIN} and ${DOB_MAX}.`);
      return;
    }
    const manualLoc = resolveLocation();
    if ((latInput || lonInput) && !manualLoc) {
      setErr("Latitude must be between -90 and 90 and longitude between -180 and 180.");
      return;
    }
    const history: History = {
      conditions: conditions.split(",").map((x) => x.trim()).filter(Boolean),
      medications: medications.split(",").map((x) => x.trim()).filter(Boolean),
      allergies: allergies.split(",").map((x) => x.trim()).filter(Boolean),
      blood_group: bloodGroup,
      notes: notes || null,
    };
    try {
      await register.mutateAsync({
        email,
        password,
        username: username || undefined,
        full_name: fullName || undefined,
        date_of_birth: dob || undefined,
        sex,
        location: manualLoc || undefined,
        history,
      });
      navigate("/", { replace: true });
    } catch (e) {
      setErr(apiErrorMessage(e));
    }
  }

  return (
    <div className="max-w-xl mx-auto px-6 py-12">
      <div className="glass p-8">
        <h1 className="text-2xl font-bold">Create your account</h1>
        <Stepper step={step} />

        {step === 1 && (
          <div className="mt-6 space-y-4">
            <Field label="Email">
              <input type="email" className="w-full" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </Field>
            <Field label="Username">
              <div className="flex gap-2">
                <input
                  className="flex-1"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="pick one, or generate"
                  autoComplete="username"
                />
                <button
                  type="button"
                  onClick={rollUsername}
                  className="btn-ghost shrink-0"
                  title="Generate a random username"
                >
                  <Shuffle className="w-4 h-4" />
                  Generate
                </button>
              </div>
              {username && !usernameValid && (
                <div className="mt-1 text-xs text-red-700">
                  3-30 chars, start with a letter, only letters/digits/_/-.
                </div>
              )}
            </Field>
            <Field label="Password (min 8 characters)">
              <input type="password" minLength={8} className="w-full" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
            </Field>
            <Field label="Confirm password">
              <input type="password" minLength={8} className="w-full" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
            </Field>
            <NavRow>
              <span />
              <button
                className="btn-primary"
                disabled={
                  !email ||
                  password.length < 8 ||
                  password !== confirm ||
                  !usernameValid
                }
                onClick={() => setStep(2)}
              >
                Continue
              </button>
            </NavRow>
          </div>
        )}

        {step === 2 && (
          <div className="mt-6 space-y-4">
            <Field label="Full name">
              <input className="w-full" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
            </Field>
            <Field label={`Date of birth (between ${DOB_MIN.slice(0, 4)} and ${DOB_MAX.slice(0, 4)})`}>
              <input
                type="date"
                className="w-full"
                value={dob}
                min={DOB_MIN}
                max={DOB_MAX}
                onChange={(e) => setDob(e.target.value)}
              />
              {dob && !dobValid && (
                <div className="mt-1 text-xs text-red-700">
                  Year must be between {DOB_MIN.slice(0, 4)} and {DOB_MAX.slice(0, 4)}.
                </div>
              )}
            </Field>
            <Field label="Sex">
              <select className="w-full" value={sex} onChange={(e) => setSex(e.target.value as Sex)}>
                <option value="prefer_not_to_say">Prefer not to say</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <NavRow>
              <button className="btn-ghost" onClick={() => setStep(1)}>Back</button>
              <button
                className="btn-primary"
                disabled={!dobValid}
                onClick={() => setStep(3)}
              >
                Continue
              </button>
            </NavRow>
          </div>
        )}

        {step === 3 && (
          <div className="mt-6 space-y-4">
            <Field label="Blood group">
              <select
                className="w-full"
                value={bloodGroup}
                onChange={(e) => setBloodGroup(e.target.value as BloodGroup)}
              >
                {BLOOD_GROUPS.map((b) => (
                  <option key={b} value={b}>
                    {b === "unknown" ? "Unknown / prefer not to say" : b}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Pre-existing conditions (optional, comma-separated)">
              <input
                className="w-full"
                value={conditions}
                onChange={(e) => setConditions(e.target.value)}
                placeholder="e.g. hypertension, diabetes, asthma"
              />
            </Field>
            <Field label="Medications (optional, comma-separated)">
              <input
                className="w-full"
                value={medications}
                onChange={(e) => setMedications(e.target.value)}
                placeholder="e.g. metformin, lisinopril"
              />
            </Field>
            <Field label="Allergies (optional, comma-separated)">
              <input
                className="w-full"
                value={allergies}
                onChange={(e) => setAllergies(e.target.value)}
                placeholder="e.g. penicillin, peanuts"
              />
            </Field>
            <Field label="Notes (optional)">
              <textarea className="w-full min-h-[80px]" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            <Field label="Location (optional, used for nearby specialist recommendations)">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <input
                  type="number"
                  step="0.000001"
                  min={-90}
                  max={90}
                  className="w-full"
                  value={latInput}
                  onChange={(e) => setLatInput(e.target.value)}
                  placeholder="Latitude (e.g. 27.7172)"
                />
                <input
                  type="number"
                  step="0.000001"
                  min={-180}
                  max={180}
                  className="w-full"
                  value={lonInput}
                  onChange={(e) => setLonInput(e.target.value)}
                  placeholder="Longitude (e.g. 85.3240)"
                />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <button type="button" className="btn-ghost" onClick={requestLocation}>
                  {loc ? "Update from device" : "Share my location"}
                </button>
                {geoMsg && <span className="text-sm text-muted">{geoMsg}</span>}
              </div>
            </Field>

            {err && <div className="text-red-700 text-sm">{err}</div>}

            <NavRow>
              <button className="btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn-primary" disabled={register.isPending} onClick={submit}>
                {register.isPending ? "Creating…" : "Create account"}
              </button>
            </NavRow>
          </div>
        )}

        <div className="mt-6 text-sm text-muted text-center">
          Already have an account?{" "}
          <Link to="/login" className="text-primary hover:underline">Sign in</Link>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm text-muted">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function NavRow({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center justify-between pt-2">{children}</div>;
}

function Stepper({ step }: { step: Step }) {
  const steps = ["Account", "About you", "Health"];
  return (
    <div className="mt-4 flex items-center gap-2 text-xs text-muted">
      {steps.map((s, i) => {
        const idx = (i + 1) as Step;
        const active = step === idx;
        const done = step > idx;
        return (
          <div key={s} className="flex items-center gap-2">
            <span
              className={
                "w-6 h-6 rounded-full grid place-items-center border " +
                (active
                  ? "bg-primary text-white border-primary"
                  : done
                    ? "bg-primary/20 border-primary/50 text-primary"
                    : "border-border/70")
              }
            >
              {idx}
            </span>
            <span className={active ? "text-text" : ""}>{s}</span>
            {idx < 3 && <span className="opacity-30">—</span>}
          </div>
        );
      })}
    </div>
  );
}
