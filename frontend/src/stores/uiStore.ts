import { create } from 'zustand';

interface UiState {
  /** Desktop: sidebar shown as a narrow icon rail instead of full width. */
  collapsed: boolean;
  /** Mobile: the temporary overlay drawer is open. */
  mobileOpen: boolean;
  toggleCollapsed: () => void;
  setMobileOpen: (open: boolean) => void;
}

/**
 * Shared UI/layout state.
 *
 * The sidebar (menu), header and content area all read from here so the layout
 * stays coordinated — collapsing the rail resizes the header and content in
 * lockstep, which the old per-component local state could not do.
 */
export const useUiStore = create<UiState>((set) => ({
  collapsed: false,
  mobileOpen: false,
  toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),
  setMobileOpen: (open) => set({ mobileOpen: open }),
}));
