import { AlertCircle, CheckCircle2, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

const styles = {
  error: 'border-destructive/40 bg-red-50 text-red-900',
  info: 'border-primary/30 bg-accent text-accent-foreground',
  success: 'border-primary/30 bg-secondary text-secondary-foreground',
}
const icons = { error: AlertCircle, info: Info, success: CheckCircle2 }

export function Alert({ variant = 'info', title, children, className }) {
  const Icon = icons[variant]
  return (
    <div role={variant === 'error' ? 'alert' : 'status'} className={cn('flex gap-3 rounded-md border p-3 text-sm', styles[variant], className)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      <div>
        {title && <p className="font-medium">{title}</p>}
        <div>{children}</div>
      </div>
    </div>
  )
}
