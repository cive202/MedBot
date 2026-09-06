import { useEffect, useState } from "react";
import { Shuffle } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useUpdateMe } from "@/lib/queries";
import { apiErrorMessage } from "@/lib/api";
import { generateUsername, isValidUsername } from "@/lib/username";
import HealthCard from "@/components/HealthCard";
import {
  BLOOD_GROUPS,
  type BloodGroup,
  type History,
  type Location,
  type Sex,
} from "@/types/user";

const DOB_MIN = "1920-01-01";
const DOB_MAX = "2026-12-31";

export default function Profile() {
  const { user } = useAuth();
  const updateMe = useUpdateMe();

  const [editing, setEditing] = useState(false);
  const [username, setUsername] = useState("");
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
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!user) return;
    setUsername(user.username ?? "");
    setFullName(user.full_name ?? "");
    setDob(user.date_of_birth ?? "");
    setSex(user.sex ?? "prefer_not_to_say");
    setBloodGroup((user.history?.blood_group as BloodGroup | undefined) ?? "unknown");
    setConditions((user.history?.conditions ?? []).join(", "));
    setMedications((user.history?.medications ?? []).join(", "));
    setAllergies((user.history?.allergies ?? []).join(", "));
    setNotes(user.history?.notes ?? "");
    setLoc(user.location ?? null);
    if (user.location) {
      setLatInput(user.location.lat.toFixed(6));
      setLonInput(user.location.lon.toFixed(6));
    } else {
      setLatInput("");
      setLonInput("");
    }
  }, [user]);

  if (!user) return null;

  const usernameValid = username === "" || isValidUsername(username);
  const dobValid = dob === "" || (dob >= DOB_MIN && dob <= DOB_MAX);

  function rollUsername() {
    setUsername(generateUsername());
  }

  function requestLocation() {
    if (!navigator.geolocation) {
      setGeoMsg("Geolocation not supported.");
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

  async function save() {
    setErr(null);
    setSaved(false);
    if (!usernameValid) {
      setErr("Username must be 3-30 chars, start with a letter, only letters/digits/_/-.");
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
      await updateMe.mutateAsync({
        username: username || undefined,
        full_name: fullName || undefined,
        date_of_birth: dob || undefined,
        sex,
        location: manualLoc || undefined,
        history,
      });
      setSaved(true);
      setEditing(false);
    } catch (e) {
      setErr(apiErrorMessage(e));
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10 space-y-6">
      <HealthCard
        user={{
          ...user,
          username: username || user.username,
          full_name: fullName || user.full_name,
          date_of_birth: dob || user.date_of_birth,
          sex,
          history: {
            conditions: conditions.split(",").map((x) => x.trim()).filter(Boolean),
            medications: medications.split(",").map((x) => x.trim()).filter(Boolean),
            allergies: allergies.split(",").map((x) => x.trim()).filter(Boolean),
            blood_group: bloodGroup,
            notes: notes || null,
          },
        }}
      />

      <div className="glass p-8 space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Your profile</h1>
          {!editing && (
            <button className="btn-ghost" onClick={() => setEditing(true)}>
              Edit
            </button>
          )}
        </div>
        {saved && <div className="text-emerald-700 text-sm">Saved.</div>}

        {!editing ? (
          <ReadView
            email={user.email}
            username={username}
            full_name={fullName}
            date_of_birth={dob}
            sex={sex}
            blood_group={bloodGroup}
            location={loc}
            conditions={conditions.split(",").map((x) => x.trim()).filter(Boolean)}
            medications={medications.split(",").map((x) => x.trim()).filter(Boolean)}
            allergies={allergies.split(",").map((x) => x.trim()).filter(Boolean)}
            notes={notes}
          />
        ) : (
          <div className="space-y-4">
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
            <Field label="Full name">
              <input className="w-full" value={fullName} onChange={(e) => setFullName(e.target.value)} />
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
            <Field label="Conditions (optional, comma-separated)">
              <input className="w-full" value={conditions} onChange={(e) => setConditions(e.target.value)} placeholder="e.g. hypertension, asthma" />
            </Field>
            <Field label="Medications (optional, comma-separated)">
              <input className="w-full" value={medications} onChange={(e) => setMedications(e.target.value)} placeholder="e.g. metformin" />
            </Field>
            <Field label="Allergies (optional, comma-separated)">
              <input className="w-full" value={allergies} onChange={(e) => setAllergies(e.target.value)} placeholder="e.g. penicillin" />
            </Field>
            <Field label="Notes">
              <textarea className="w-full min-h-[80px]" value={notes} onChange={(e) => setNotes(e.target.value)} />
            </Field>
            <Field label="Location (optional)">
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

            <div className="flex items-center gap-3 pt-2">
              <button className="btn-primary" disabled={updateMe.isPending} onClick={save}>
                {updateMe.isPending ? "Saving…" : "Save"}
              </button>
              <button className="btn-ghost" onClick={() => setEditing(false)} disabled={updateMe.isPending}>
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="text-xs text-muted pt-4 border-t border-border/60">
          History is encrypted at rest with Fernet using your <code>FERNET_KEY</code>.
        </div>
      </div>
    </div>
  );
}

function ReadView(props: {
  email: string;
  username?: string | null;
  full_name?: string | null;
  date_of_birth?: string | null;
  sex?: string | null;
  blood_group?: BloodGroup | null;
  location?: Location | null;
  conditions: string[];
  medications: string[];
  allergies: string[];
  notes?: string | null;
}) {
  return (
    <div className="space-y-3">
      <Row k="Username" v={props.username ? `@${props.username}` : "—"} />
      <Row k="Email" v={props.email} />
      <Row k="Name" v={props.full_name || "—"} />
      <Row k="Date of birth" v={props.date_of_birth || "—"} />
      <Row k="Sex" v={props.sex || "—"} />
      <Row
        k="Blood group"
        v={props.blood_group && props.blood_group !== "unknown" ? props.blood_group : "—"}
      />
      <Row
        k="Location"
        v={
          props.location
            ? `${props.location.lat.toFixed(3)}, ${props.location.lon.toFixed(3)}`
            : "—"
        }
      />
      <ChipRow label="Conditions" items={props.conditions} />
      <ChipRow label="Medications" items={props.medications} />
      <ChipRow label="Allergies" items={props.allergies} />
      {props.notes && (
        <div>
          <div className="text-sm text-muted">Notes</div>
          <div className="text-sm">{props.notes}</div>
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/40 pb-2">
      <span className="text-muted text-sm">{k}</span>
      <span className="text-sm">{v}</span>
    </div>
  );
}

function ChipRow({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <div className="text-sm text-muted mb-1">{label}</div>
      <div className="flex flex-wrap gap-2">
        {items.length === 0 && <span className="text-muted text-sm">None recorded</span>}
        {items.map((c) => (
          <span
            key={c}
            className="px-3 py-1 rounded-full bg-white/80 border border-border/70 text-sm"
          >
            {c}
          </span>
        ))}
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
