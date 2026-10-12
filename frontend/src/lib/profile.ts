import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";

import {api} from "./api";

export type Profile = {user_id: string; exists: boolean; name: string | null; timezone: string; city: string; lat: number | null; lng: number | null; home: string | null; work: string | null; on_time_target: number; source: "person" | "deployment default"; local_time: string};
export type ProfileEdit = Partial<Pick<Profile, "name" | "timezone" | "city" | "lat" | "lng" | "home" | "work" | "on_time_target">>;

/** One person per browser until accounts arrive: an id generated once and kept; it is what the server files everything under. */
export {stableUserId} from "./userId";

export const browserZone = () => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone; } catch { return "UTC"; } };

export function useProfile(userId: string) {
  return useQuery({queryKey: ["profile", userId], queryFn: () => api.profile(userId) as Promise<Profile>, staleTime: 60_000});
}

export function useSaveProfile(userId: string) {
  const qc = useQueryClient();
  return useMutation({mutationFn: (edit: ProfileEdit) => api.saveProfile(userId, edit) as Promise<Profile>, onSuccess: () => { qc.invalidateQueries({queryKey: ["profile", userId]}); qc.invalidateQueries({queryKey: ["plan"]}); }});
}

/** The city at the browser's position, from the server's reverse geocoder; rejects when the person declines or the lookup fails. */
export function locateMe(): Promise<{lat: number; lng: number; city: string; country?: string; display_name?: string}> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error("this browser has no location service"));
    navigator.geolocation.getCurrentPosition(
      (pos) => api.locate(pos.coords.latitude, pos.coords.longitude).then((r) => resolve(r as {lat: number; lng: number; city: string})).catch(reject),
      (err) => reject(new Error(err.message || "location was not shared")), {timeout: 15_000, maximumAge: 300_000});
  });
}
