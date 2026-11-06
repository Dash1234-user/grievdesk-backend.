import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Logo } from '@/components/Logo'
import { Button } from '@/components/ui/button'

const env = import.meta.env

function Contact({ label, value, href }) {
  const { t } = useTranslation()
  const body = (
    <>
      <div className="text-sm">{label}</div>
      <div className="font-semibold">{value || t('landing.notSet')}</div>
    </>
  )
  const cls = 'min-h-11 rounded-md bg-red-50 px-3.5 py-3 text-red-900'
  return href && value ? <a href={href} className={cls}>{body}</a> : <div className={cls}>{body}</div>
}

export default function Landing() {
  const { t } = useTranslation()
  const steps = ['step1', 'step2', 'step3']

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col">
      <header className="border-b bg-card px-5 py-4">
        <Logo subtitle={t('landing.helpDesk')} />
      </header>

      <section className="flex flex-col gap-3.5 px-5 pb-6 pt-7">
        <h1 className="text-3xl font-bold leading-tight">{t('landing.tagline')}</h1>
        <p className="leading-relaxed text-muted-foreground">{t('landing.intro')}</p>
        <Button asChild size="lg"><Link to="/login">{t('landing.login')}</Link></Button>
        <Button asChild size="lg" variant="outline"><Link to="/register">{t('landing.register')}</Link></Button>
        <p className="text-sm text-muted-foreground">{t('landing.verifyNote')}</p>
      </section>

      <section className="px-5 pb-6">
        <h2 className="mb-3 text-lg font-semibold">{t('landing.howTitle')}</h2>
        <ol className="flex flex-col gap-2.5">
          {steps.map((s, i) => (
            <li key={s} className="flex items-center gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary font-semibold text-secondary-foreground">{i + 1}</span>
              <span>{t(`landing.${s}`)}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="px-5 pb-6">
        <h2 className="mb-3 text-lg font-semibold">{t('landing.emergencyTitle')}</h2>
        <div className="grid grid-cols-2 gap-2.5">
          <Contact label={t('landing.security')} value={env.VITE_SECURITY_PHONE} href={`tel:${env.VITE_SECURITY_PHONE}`} />
          <Contact label={t('landing.fire')} value="101" href="tel:101" />
          <Contact label={t('landing.ambulance')} value="102" href="tel:102" />
          <Contact label={t('landing.lift')} value={env.VITE_LIFT_PHONE} href={`tel:${env.VITE_LIFT_PHONE}`} />
        </div>
      </section>

      <footer className="mt-auto border-t bg-card px-5 py-4 text-sm text-muted-foreground">
        {t('landing.committee')}: {env.VITE_COMMITTEE_EMAIL || t('landing.notSet')} · {t('landing.officeHours')}: {env.VITE_OFFICE_HOURS || t('landing.notSet')}
      </footer>
    </div>
  )
}
