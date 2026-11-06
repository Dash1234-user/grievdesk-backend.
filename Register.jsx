import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { errorMessage } from '@/lib/i18n'
import { LANGUAGES } from '@/lib/constants'
import { Logo } from '@/components/Logo'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label, Select } from '@/components/ui/input'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_RE = /^\+?[0-9][0-9 -]{5,18}[0-9]$/ // same rule the backend uses when you edit your profile

const empty = { name: '', phone: '', flat_no: '', block_no: '', gmail: '', preferred_language: 'en', password: '', confirm: '' }

export default function Register() {
  const { t } = useTranslation()
  const { register } = useAuth()
  const [f, setF] = useState(empty)
  const [secretary, setSecretary] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null) // 'resident' | 'secretary'

  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }))

  function validate() {
    if (['name', 'phone', 'flat_no', 'block_no', 'gmail', 'password'].some((k) => !f[k].trim())) return t('validation.required')
    if (!EMAIL_RE.test(f.gmail.trim())) return t('validation.email')
    if (!PHONE_RE.test(f.phone.trim())) return t('validation.phone')
    if (f.password.length < 8) return t('validation.passwordShort')
    if (f.password !== f.confirm) return t('validation.passwordMismatch')
    return null
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError(null)
    const problem = validate()
    if (problem) {
      setError({ code: 'validation', message: problem })
      return
    }
    setBusy(true)
    try {
      await register({
        role: secretary ? 'admin' : 'resident', // the backend calls the Secretary role "admin" at sign-up
        name: f.name.trim(),
        phone: f.phone.trim(),
        flat_no: f.flat_no.trim(),
        block_no: f.block_no.trim(),
        gmail: f.gmail.trim(),
        preferred_language: f.preferred_language,
        password: f.password,
      })
      setDone(secretary ? 'secretary' : 'resident')
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-5 py-8">
        <Logo />
        <Alert variant="success" title={done === 'secretary' ? t('auth.secretaryDoneTitle') : t('auth.pendingTitle')}>
          {done === 'secretary' ? t('auth.secretaryDoneBody') : t('auth.pendingBody')}
        </Alert>
        <Button asChild><Link to="/login">{t('auth.goToLogin')}</Link></Button>
      </div>
    )
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-5 py-8">
      <Logo />
      <Card>
        <CardHeader>
          <CardTitle>{t('auth.registerTitle')}</CardTitle>
          <CardDescription>{t('auth.registerSubtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            {error && <Alert variant="error">{error.code === 'validation' ? error.message : errorMessage(t, error)}</Alert>}
            <div className="flex flex-col gap-2">
              <Label htmlFor="name">{t('auth.name')}</Label>
              <Input id="name" autoComplete="name" value={f.name} onChange={set('name')} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="gmail">{t('auth.gmail')}</Label>
              <Input id="gmail" type="email" autoComplete="email" inputMode="email" placeholder="name@gmail.com" value={f.gmail} onChange={set('gmail')} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="phone">{t('auth.phone')}</Label>
              <Input id="phone" type="tel" autoComplete="tel" inputMode="tel" placeholder="+91 98765 43210" value={f.phone} onChange={set('phone')} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-2">
                <Label htmlFor="block_no">{t('auth.block')}</Label>
                <Input id="block_no" placeholder="B" value={f.block_no} onChange={set('block_no')} />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="flat_no">{t('auth.flat')}</Label>
                <Input id="flat_no" placeholder="304" value={f.flat_no} onChange={set('flat_no')} />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="lang">{t('auth.language')}</Label>
              <Select id="lang" value={f.preferred_language} onChange={set('preferred_language')}>
                {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">{t('auth.password')}</Label>
              <Input id="password" type="password" autoComplete="new-password" value={f.password} onChange={set('password')} />
              <p className="text-xs text-muted-foreground">{t('auth.passwordHint')}</p>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="confirm">{t('auth.confirmPassword')}</Label>
              <Input id="confirm" type="password" autoComplete="new-password" value={f.confirm} onChange={set('confirm')} />
            </div>
            <label className="flex items-start gap-3 text-sm">
              <input type="checkbox" className="mt-1 h-4 w-4" checked={secretary} onChange={(e) => setSecretary(e.target.checked)} />
              <span>
                {t('auth.secretaryToggle')}
                <span className="block text-muted-foreground">{t('auth.secretaryHelp')}</span>
              </span>
            </label>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {busy ? t('auth.registering') : t('auth.registerButton')}
            </Button>
          </form>
        </CardContent>
      </Card>
      <p className="text-center text-sm text-muted-foreground">
        {t('auth.haveAccount')}{' '}
        <Link to="/login" className="font-medium text-primary underline">{t('auth.loginLink')}</Link>
      </p>
    </div>
  )
}
