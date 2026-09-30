import { createApp } from 'vue'

import App from './App.vue'
import './styles.css'
import './design-tokens.css'
import { applyTheme, readStoredTheme } from './shared/hooks/useTheme.js'

// Apply the stored (or default light) theme before mount to avoid a flash of
// the wrong theme on load.
applyTheme(readStoredTheme())

createApp(App).mount('#app')
