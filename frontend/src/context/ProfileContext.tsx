import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Profile } from "../api/types";

const STORAGE_KEY = "dap.shopper.profile";
const SHOPPER_ID_KEY = "dap.shopper.id";

const DEFAULT_PROFILE: Profile = {
  age: null,
  gender: null,
  budget_band: null,
  max_budget: null,
  location: null,
};

function getOrCreateShopperId(): string {
  const existing = localStorage.getItem(SHOPPER_ID_KEY);
  if (existing) return existing;
  const id = crypto.randomUUID();
  localStorage.setItem(SHOPPER_ID_KEY, id);
  return id;
}

interface ProfileContextValue {
  profile: Profile;
  setProfile: (p: Profile) => void;
  shopperId: string;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfileState] = useState<Profile>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_PROFILE, ...JSON.parse(raw) } : DEFAULT_PROFILE;
  });
  const [shopperId] = useState<string>(getOrCreateShopperId);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  }, [profile]);

  const setProfile = (p: Profile) => setProfileState(p);

  return (
    <ProfileContext.Provider value={{ profile, setProfile, shopperId }}>
      {children}
    </ProfileContext.Provider>
  );
}

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}
