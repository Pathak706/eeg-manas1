import axios from 'axios'

// In production, VITE_API_URL is set to the Railway backend internal/public URL.
// In dev, Vite proxies /api → localhost:8000 (see vite.config.ts).
const baseURL = import.meta.env.VITE_API_URL || '/api'

const client = axios.create({
  baseURL,
  timeout: 60_000,
})

export default client
