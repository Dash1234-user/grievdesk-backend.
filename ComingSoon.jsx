import { useTranslation } from 'react-i18next'
import { Hammer } from 'lucide-react'
import { useAuth } from '@/lib/auth'

// Placeholder for screens that arrive in later build steps.
export default function ComingSoon({ title, step }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  return (
    <div className="mx-auto max-w-xl p-6">
      <div className="flex items-center gap-3">
        <Hammer className="h-6 w-6 text-primary" aria-hidden="true" />
        <h1 className="text-2xl font-semibold">{title}</h1>
      </div>
      <p className="mt-4 font-medium">{t('comingSoon.title', { step })}</p>
      <p className="mt-1 text-muted-foreground">{t('comingSoon.body')}</p>
      {user && (
        <p className="mt-4 rounded-md bg-secondary p-3 text-sm text-secondary-foreground">
          {t('comingSoon.signedInAs', { name: user.name, role: t(`roles.${user.role}`), flat: user.flat_no, block: user.block_no })}
        </p>
      )}
    </div>
  )
}
