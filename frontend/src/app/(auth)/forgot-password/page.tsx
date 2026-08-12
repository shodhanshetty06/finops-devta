"use client";

import { ArrowLeft, Loader2, Mail } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setIsSubmitting(true);
    // There is no password-reset endpoint on the backend yet (see
    // backend/app/api/routers/auth.py - register/login/me only), so this
    // deliberately does not call an API that doesn't exist. Rather than
    // fake a "check your email" flow with nothing behind it, this is
    // upfront about the real state and points to a working alternative.
    setTimeout(() => {
      setIsSubmitting(false);
      setSubmitted(true);
    }, 400);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">Reset your password</h1>
        <p className="text-sm text-muted-foreground">Enter the email on your account and we&apos;ll help you get back in.</p>
      </div>

      {submitted ? (
        <Alert variant="info" title="Self-service reset isn't available yet">
          Password resets aren&apos;t wired up to an email provider in this environment. Contact your organization&apos;s admin
          to have your password reset directly, or if you know it, log in and change it from Settings.
        </Alert>
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="email">Email</Label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
            Send reset instructions
          </Button>
        </form>
      )}

      <Link href="/login" className="flex items-center justify-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to log in
      </Link>
    </div>
  );
}
