import { redirect } from "next/navigation";

// Auth is not yet wired. The /login route is reserved for the future
// authenticated app shell. For now, send visitors to the marketing home
// so the URL doesn't 404 (it was previously listed in the sitemap).
export default function LoginPage(): never {
  redirect("/");
}
