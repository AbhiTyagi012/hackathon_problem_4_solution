import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Profile } from "../api/types";

const STORAGE_KEY = "dap.shopper.profile";

const DEFAULT_PROFILE: Profile = {
  age: null,
  gender: null,
  interests: [],
  budget_band: null,
  max_budget: null,
  location: null,
  past_purchase_categories: [],
};

interface ProfileContextValue {
  profile: Profile;
  setProfile: (p: Profile) => void;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfileState] = useState<Profile>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_PROFILE, ...JSON.parse(raw) } : DEFAULT_PROFILE;
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  }, [profile]);

  const setProfile = (p: Profile) => setProfileState(p);

  return (
    <ProfileContext.Provider value={{ profile, setProfile }}>{children}</ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}
