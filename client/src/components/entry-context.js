import { createContext, useContext } from 'react';

export const EntryContext = createContext(null);

export function useEntry() {
  return useContext(EntryContext);
}
