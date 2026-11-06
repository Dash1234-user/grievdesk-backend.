import { SOCIETY_NAME } from '@/lib/constants'

export function Logo({ subtitle }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary text-xl font-bold text-primary-foreground" aria-hidden="true">
        {(SOCIETY_NAME.trim()[0] || 'G').toUpperCase()}
      </div>
      <div className="leading-tight">
        <div className="font-semibold">{SOCIETY_NAME}</div>
        {subtitle && <div className="text-sm text-muted-foreground">{subtitle}</div>}
      </div>
    </div>
  )
}
