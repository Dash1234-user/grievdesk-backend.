// The backend stores everything in English and adds "<field>_local" for readers who prefer another language.
// Always read text through this helper so the translation is used when it exists.
export function local(item, field) {
  if (!item) return ''
  return item[`${field}_local`] ?? item[field] ?? ''
}
