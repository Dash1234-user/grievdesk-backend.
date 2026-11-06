import * as React from 'react'
import { cn } from '@/lib/utils'

const Input = React.forwardRef(({ className, type = 'text', ...props }, ref) => (
  <input
    type={type}
    ref={ref}
    className={cn(
      'flex h-11 w-full rounded-md border border-input bg-card px-3 text-base placeholder:text-muted-foreground disabled:opacity-60',
      className,
    )}
    {...props}
  />
))
Input.displayName = 'Input'

const Select = React.forwardRef(({ className, children, ...props }, ref) => (
  <select
    ref={ref}
    className={cn('flex h-11 w-full rounded-md border border-input bg-card px-3 text-base', className)}
    {...props}
  >
    {children}
  </select>
))
Select.displayName = 'Select'

function Label({ className, ...props }) {
  return <label className={cn('text-sm font-medium leading-none', className)} {...props} />
}

export { Input, Select, Label }
