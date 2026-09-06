export type Sex = "male" | "female" | "other" | "prefer_not_to_say";

export type BloodGroup =
  | "A+"
  | "A-"
  | "B+"
  | "B-"
  | "AB+"
  | "AB-"
  | "O+"
  | "O-"
  | "unknown";

export const BLOOD_GROUPS: BloodGroup[] = [
  "A+",
  "A-",
  "B+",
  "B-",
  "AB+",
  "AB-",
  "O+",
  "O-",
  "unknown",
];

export interface Location {
  lat: number;
  lon: number;
  label?: string | null;
}

export interface History {
  conditions: string[];
  medications: string[];
  allergies: string[];
  blood_group?: BloodGroup | null;
  notes?: string | null;
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  username?: string | null;
  full_name?: string | null;
  date_of_birth?: string | null; // ISO date
  sex?: Sex | null;
  location?: Location | null;
  history?: History | null;
}
