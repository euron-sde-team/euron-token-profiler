"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import { AuthLayout } from "@/components/auth/auth-layout";
import { Button } from "@/components/ui/button";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { safeNext } from "@/lib/navigation";
import { useLogin, useSystemInfo } from "@/lib/queries";
import { runtimeEnv } from "@/lib/runtime-env";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const system = useSystemInfo();
  const login = useLogin({ silent: true });
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // A fresh deployment has no accounts: the first one is created on the welcome page.
  useEffect(() => {
    if (system.data?.needs_setup) router.replace("/welcome");
  }, [system.data, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await login.mutateAsync({ email, password });
      router.replace(safeNext(params.get("next")));
    } catch {
      // The error is rendered from the mutation state.
    }
  }

  return (
    <form onSubmit={submit} className="w-full space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
        <p className="text-muted-foreground mt-1.5 text-[13.5px]">
          Sign in to explore traces, costs, prompts and alerts.
        </p>
      </div>
      <Field label="Email" htmlFor="email">
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          autoFocus
        />
      </Field>
      <Field label="Password" htmlFor="password">
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </Field>
      {login.error ? <ErrorNotice message={login.error.message} /> : null}
      <Button type="submit" size="lg" className="w-full" loading={login.isPending}>
        Sign in
      </Button>
      <p className="text-muted-foreground text-center text-[13px]">
        No account? Ask an administrator to create one for you.
      </p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <AuthLayout productName={runtimeEnv().productName}>
      <Suspense fallback={<Spinner />}>
        <LoginForm />
      </Suspense>
    </AuthLayout>
  );
}
