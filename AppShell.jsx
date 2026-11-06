import { useState } from 'react'
import { NavLink, Outlet, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  Bell, CalendarDays, Inbox, LogOut, Megaphone, Menu, MessageSquarePlus,
  Search, ShieldCheck, Ticket, UserCircle, Users, Wallet, Wrench, X,
} from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { Logo } from '@/components/Logo'
import { cn } from '@/lib/utils'

// Which screens each role sees. Staff = committee or secretary.
const NAV = [
  { to: '/chat', icon: MessageSquarePlus, key: 'chat' },
  { to: '/inbox', icon: Inbox, key: 'inbox' },
  { to: '/my-tickets', icon: Ticket, key: 'myTickets' },
  { to: '/announcements', icon: Megaphone, key: 'announcements' },
  { to: '/dues', icon: Wallet, key: 'dues' },
  { to: '/amenities', icon: CalendarDays, key: 'amenities' },
  { to: '/directory', icon: Users, key: 'directory' },
  { to: '/committee', icon: Wrench, key: 'committee', staffOnly: true },
  { to: '/secretary', icon: ShieldCheck, key: 'secretary', secretaryOnly: true },
]

function SidebarContent({ onNavigate }) {
  const { t } = useTranslation()
  const { user, isStaff, isSecretary, logout } = useAuth()
  const items = NAV.filter((i) => (!i.staffOnly || isStaff) && (!i.secretaryOnly || isSecretary))

  return (
    <div className="flex h-full flex-col">
      <div className="p-4"><Logo /></div>
      <nav className="flex flex-col gap-1 px-3" aria-label="Main">
        {items.map(({ to, icon: Icon, key }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium hover:bg-accent',
                isActive && 'bg-secondary text-secondary-foreground',
              )
            }
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            {t(`nav.${key}`)}
          </NavLink>
        ))}
      </nav>
      <div className="mt-4 flex-1 overflow-y-auto px-6">
        <h2 className="text-sm font-medium text-muted-foreground">{t('nav.recents')}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{t('nav.recentsEmpty')}</p>
      </div>
      <div className="border-t p-3">
        <Link to="/profile" onClick={onNavigate} className="flex min-h-11 items-center gap-3 rounded-md px-3 hover:bg-accent">
          <UserCircle className="h-8 w-8 shrink-0 text-primary" aria-hidden="true" />
          <span className="min-w-0 leading-tight">
            <span className="block truncate text-sm font-medium">{user?.name}</span>
            <span className="block truncate text-xs text-muted-foreground">
              {t(`roles.${user?.role}`)} · {user?.block_no}-{user?.flat_no}
            </span>
          </span>
        </Link>
        <button
          onClick={() => logout()}
          className="mt-1 flex min-h-11 w-full items-center gap-3 rounded-md px-3 text-sm font-medium hover:bg-accent"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          {t('nav.logout')}
        </button>
      </div>
    </div>
  )
}

export function AppShell() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  return (
    <div className="flex h-screen bg-background">
      <aside className="hidden w-72 shrink-0 border-r bg-card md:block">
        <SidebarContent />
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85%] bg-card shadow-lg">
            <button
              onClick={() => setOpen(false)}
              className="absolute right-2 top-2 flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent"
              aria-label={t('nav.closeMenu')}
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-card px-3">
          <button
            onClick={() => setOpen(true)}
            className="flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent md:hidden"
            aria-label={t('nav.openMenu')}
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
          <div className="flex-1" />
          <Link to="/search" className="flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent" aria-label={t('nav.search')}>
            <Search className="h-5 w-5" aria-hidden="true" />
          </Link>
          <Link to="/notifications" className="flex h-10 w-10 items-center justify-center rounded-md hover:bg-accent" aria-label={t('nav.notifications')}>
            <Bell className="h-5 w-5" aria-hidden="true" />
          </Link>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
