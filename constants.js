export const SOCIETY_NAME = import.meta.env.VITE_SOCIETY_NAME || 'Your Society Name'

export const ROLES = { RESIDENT: 'resident', COMMITTEE: 'committee', SECRETARY: 'secretary' }

export const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'or', label: 'ଓଡ଼ିଆ' },
]

// These values must match the backend exactly (app/models/*.py).
export const COMPLAINT_STATUSES = ['new', 'in_progress', 'resolved', 'escalated']
export const SERVICE_STATUSES = ['new', 'in_progress', 'resolved']
export const CATEGORIES = ['Plumbing', 'Electrical', 'Water Supply', 'Sanitation', 'Parking', 'Noise', 'Security', 'Other']
export const SEVERITIES = ['low', 'medium', 'high']
export const SERVICE_TYPES = ['plumber', 'electrician', 'ac_mechanic', 'laundry', 'vehicle_service']
export const CHAT_TYPES = ['complaint', 'service', 'rules', 'committee_action']
