/**
 * Small client-side random username generator.
 *
 * Pattern: adjective-noun-NNN, e.g. "swift-otter-482". 3-30 chars, leading
 * letter, dashes only — matches the backend USERNAME_RE.
 */

const ADJECTIVES = [
  "swift",
  "calm",
  "brave",
  "bright",
  "quiet",
  "sunny",
  "lucky",
  "kind",
  "gentle",
  "bold",
  "merry",
  "happy",
  "wise",
  "clever",
  "nimble",
  "loyal",
  "cosmic",
  "stellar",
  "amber",
  "noble",
];

const NOUNS = [
  "otter",
  "falcon",
  "fox",
  "panda",
  "tiger",
  "lynx",
  "heron",
  "willow",
  "comet",
  "river",
  "ember",
  "harbor",
  "cobalt",
  "maple",
  "puma",
  "raven",
  "atlas",
  "nimbus",
  "echo",
  "sable",
];

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function generateUsername(): string {
  const num = Math.floor(Math.random() * 1000)
    .toString()
    .padStart(3, "0");
  return `${pick(ADJECTIVES)}-${pick(NOUNS)}-${num}`;
}

export const USERNAME_RE = /^[A-Za-z][A-Za-z0-9_-]{2,29}$/;

export function isValidUsername(value: string): boolean {
  return USERNAME_RE.test(value);
}
