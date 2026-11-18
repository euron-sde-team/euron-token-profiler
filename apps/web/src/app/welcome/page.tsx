"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { AuthLayout } from "@/components/auth/auth-layout";
import { MIN_PASSWORD_LENGTH } from "@/components/shell/password-form";
import { Button } from "@/components/ui/button";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/input";
import { useSetup, useSystemInfo } from "@/lib/queries";
import { runtimeEnv } from "@/lib/runtime-env";

/** First-run setup: the first account becomes the administrator of the deployment. */
function WelcomeForm() {
  const router = useRouter();
  const system = useSystemInfo();
  const setup = useSetup({ silent: true });
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    // Once this form has created the account, setup is over: the answer that says so must
    // not send the new administrator to the sign-in page.
    if (!setup.isSuccess && system.data && !system.data.needs_setup) router.replace("/login");
  }, [setup.isSuccess, system.data, router]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      await setup.mutateAsync({ name, email, password });
      router.replace("/overview");
    } catch {
      // The error is rendered from the mutation state.
    }
  }

  if (!system.data) {
    return (
      <div className="flex justify-center" role="status" aria-label="Loading">
        <Spinner className="size-5" />
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="w-full space-y-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Set up {system.data.product_name}</h1>
        <p className="text-muted-foreground mt-1.5 text-[13.5px]">
          Create the first account. It becomes the administrator of this deployment and can invite the rest of the team.
        </p>
      </div>
      <Field label="Your name" htmlFor="name">
        <Input
          id="name"
          name="name"
          autoComplete="name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          autoFocus
        />
      </Field>
      <Field label="Email" htmlFor="email">
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
      </Field>
      <Field label="Password" htmlFor="password" hint={`At least ${MIN_PASSWORD_LENGTH} characters.`}>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="new-password"
          value={password}
          minLength={MIN_PASSWORD_LENGTH}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
      </Field>
      {setup.error ? <ErrorNotice message={setup.error.message} /> : null}
      <Button type="submit" size="lg" className="w-full" loading={setup.isPending}>
        Create the administrator account
      </Button>
    </form>
  );
}

export default function WelcomePage() {
  return (
    <AuthLayout productName={runtimeEnv().productName}>
      <WelcomeForm />
    </AuthLayout>
  );
}
