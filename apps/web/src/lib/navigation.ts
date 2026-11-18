/**
 * Where to go after signing in. Only same-origin paths are honoured: "//evil.example" and
 * "https://evil.example" would turn the sign-in page into an open redirect.
 */
export function safeNext(raw: string | null | undefined): string {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return "/overview";
  return raw;
}
