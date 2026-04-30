import { Eye, EyeOff } from "lucide-react";
import * as React from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface PasswordInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> {
  /** ARIA-correct label of the toggle button. */
  toggleLabel?: { show: string; hide: string };
}

export const PasswordInput = React.forwardRef<HTMLInputElement, PasswordInputProps>(
  ({ className, toggleLabel, ...props }, ref) => {
    const [visible, setVisible] = React.useState(false);
    const labels = toggleLabel ?? { show: "Show password", hide: "Hide password" };
    return (
      <div className="relative">
        <Input
          ref={ref}
          type={visible ? "text" : "password"}
          className={cn("pr-11", className)}
          {...props}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? labels.hide : labels.show}
          aria-pressed={visible}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-md"
          tabIndex={0}
        >
          {visible ? (
            <EyeOff className="size-4" aria-hidden="true" />
          ) : (
            <Eye className="size-4" aria-hidden="true" />
          )}
        </button>
      </div>
    );
  },
);
// NOSONAR — Sonar's S2068 hardcoded-password rule flags the identifier
// "PasswordInput" itself; this is a component name, not a credential.
PasswordInput.displayName = "PasswordInput"; // NOSONAR
