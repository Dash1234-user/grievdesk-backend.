import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { errorMessage } from '@/lib/i18n'
import { Logo } from '@/components/Logo'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input, Label } from '@/components/ui/input'

export default function Login() {
  const { t } = useTranslation()
  const { login, notice } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [gmail, setGmail] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function onSubmit(e) {
    e.preventDefault()
    setError(null)
    if (!gmail.trim() || !password) {
      setError({ message: t('validation.required'), code: 'required' })
      return
    }
    setBusy(true)
    try {
      await login(gmail.trim(), password)
      navigate(location.state?.from?.pathname || '/chat', { replace: true })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const pending = error?.code === 'pending_approval'

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 px-5 py-8">
      <Logo />
      <Card>
        <CardHeader>
          <CardTitle>{t('auth.loginTitle')}</CardTitle>
          <CardDescription>{t('auth.loginSubtitle')}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            {notice === 'sessionExpired' && !error && <Alert variant="info">{t('auth.sessionExpired')}</Alert>}
            {error && (
              <Alert variant={pending ? 'info' : 'error'}>
                {error.code === 'required' ? error.message : errorMessage(t, error)}
              </Alert>
            )}
            <div className="flex flex-col gap-2">
              <Label htmlFor="gmail">{t('auth.gmail')}</Label>
              <Input id="gmail" type="email" autoComplete="email" inputMode="email" placeholder="name@gmail.com" value={gmail} onChange={(e) => setGmail(e.target.value)} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="password">{t('auth.password')}</Label>
              <div className="relative">
                <Input id="password" type={show ? 'text' : 'password'} autoComplete="current-password" className="pr-11" value={password} onChange={(e) => setPassword(e.target.value)} />
                <button
                  type="button"
                  onClick={() => setShow((s) => !s)}
                  className="absolute right-1 top-1 flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
                  aria-label={show ? t('auth.hidePassword') : t('auth.showPassword')}
                >
                  {show ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
                </button>
              </div>
            </div>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              {busy ? t('auth.loggingIn') : t('auth.loginButton')}
            </Button>
          </form>
        </CardContent>
      </Card>
      <p className="text-center text-sm text-muted-foreground">
        {t('auth.noAccount')}{' '}
        <Link to="/register" className="font-medium text-primary underline">{t('auth.registerLink')}</Link>
      </p>
      <p className="text-center text-sm"><Link to="/" className="text-muted-foreground underline">{t('auth.backHome')}</Link></p>
    </div>
  )
}
