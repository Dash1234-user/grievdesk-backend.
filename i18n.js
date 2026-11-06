import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from '@/locales/en.json'

// Hindi (hi) and Odia (or) files are added in the translations step. Until then they fall back to English.
i18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: 'en',
  fallbackLng: 'en',
  supportedLngs: ['en', 'hi', 'or'],
  interpolation: { escapeValue: false },
})

export default i18n

// Turns an ApiError into a message in the reader's language.
export function errorMessage(t, err) {
  if (!err) return ''
  return t(`errors.${err.code}`, { defaultValue: err.message || t('errors.http_error') })
}
