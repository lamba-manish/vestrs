import type { StepStatus } from "@/components/onboarding/status-pill";

export interface OnboardingState {
  profile: StepStatus;
  kyc: StepStatus;
  accreditation: StepStatus;
  bank: StepStatus;
  invest: StepStatus;
}

export interface ProfileBits {
  full_name: string | null;
  nationality: string | null;
}

export function deriveOnboardingState(input: {
  profile?: ProfileBits;
  kycStatus?: "not_started" | "pending" | "success" | "failed";
  accreditationStatus?: "not_started" | "pending" | "success" | "failed";
  bankLinked?: boolean;
  hasInvestment?: boolean;
}): OnboardingState {
  const profile: StepStatus =
    input.profile?.full_name && input.profile.nationality ? "success" : "not_started";

  const mapAsync = (s?: "not_started" | "pending" | "success" | "failed"): StepStatus => {
    if (!s || s === "not_started") return "not_started";
    if (s === "pending") return "pending";
    if (s === "success") return "success";
    return "failed";
  };

  return {
    profile,
    kyc: mapAsync(input.kycStatus),
    accreditation: mapAsync(input.accreditationStatus),
    bank: input.bankLinked ? "success" : "not_started",
    invest: input.hasInvestment ? "success" : "not_started",
  };
}

export function nextActionLabel(s: StepStatus): string {
  switch (s) {
    case "not_started":
      return "Start";
    case "in_progress":
      return "Continue";
    case "pending":
      return "View status";
    case "failed":
      return "Retry";
    case "success":
      return "View";
  }
}
