import { ref, readonly } from 'vue'

const STORAGE_KEY = 'os-theme'
const THEMES = ['light', 'dark']
const DEFAULT_THEME = 'light'

/**
 * Read the persisted theme, falling back to the default (light) when the stored
 * value is missing or not one of the known themes.
 */
export function readStoredTheme() {
  let stored = null
  try {
    stored = localStorage.getItem(STORAGE_KEY)
  } catch {
    // localStorage may be unavailable (private mode, disabled) — use default
  }
  return THEMES.includes(stored) ? stored : DEFAULT_THEME
}

/**
 * Apply a theme to the document. Sets data-theme on <html>, which the CSS
 * palettes in styles.css key off of. Safe to call before the app mounts.
 */
export function applyTheme(theme) {
  const resolved = THEMES.includes(theme) ? theme : DEFAULT_THEME
  document.documentElement.dataset.theme = resolved
  return resolved
}

// Shared reactive state so every consumer sees the same current theme.
const current = ref(readStoredTheme())

function persist(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // ignore persistence failures — theme still applies for this session
  }
}

function set(theme) {
  const resolved = applyTheme(theme)
  current.value = resolved
  persist(resolved)
}

function toggle() {
  set(current.value === 'dark' ? 'light' : 'dark')
}

/**
 * Composable exposing the current theme and controls to change it.
 */
export function useTheme() {
  return {
    theme: readonly(current),
    set,
    toggle,
  }
}
