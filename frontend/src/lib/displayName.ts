/** The user's first name, derived from their email local-part (no separate "name" field exists
 * yet) — e.g. "john.doe@x.com" -> "John". Used anywhere the UI shows the signed-in user's name. */
export function firstNameFromEmail(email: string | null | undefined): string {
  if (!email) return "Signed out";
  const local = email.split("@")[0];
  const first = local.split(/[._-]/)[0] || local;
  return first.charAt(0).toUpperCase() + first.slice(1).toLowerCase();
}
