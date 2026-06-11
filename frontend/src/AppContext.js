import { createContext } from "react";

export const AppContext = createContext({
  imageLookup: {},
  weightClasses: [],
  openProfile: () => {},
  sendToFightLab: () => {},
  fightLabPrefill: { a: "", b: "" },
  profileFighter: "",
});
