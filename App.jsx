import { Navigate, Route, Routes } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ProtectedRoute, PublicOnlyRoute } from '@/components/ProtectedRoute'
import { AppShell } from '@/components/AppShell'
import Landing from '@/pages/Landing'
import Login from '@/pages/Login'
import Register from '@/pages/Register'
import ComingSoon from '@/pages/ComingSoon'

// [path, nav label key, build step that replaces the placeholder, allowed roles (undefined = everyone)]
const LATER_SCREENS = [
  ['chat', 'nav.chat', 3],
  ['inbox', 'nav.inbox', 6],
  ['my-tickets', 'nav.myTickets', 5],
  ['announcements', 'nav.announcements', 7],
  ['notifications', 'nav.notifications', 7],
  ['dues', 'nav.dues', 8],
  ['profile', 'nav.profile', 8],
  ['amenities', 'nav.amenities', 9],
  ['directory', 'nav.directory', 9],
  ['search', 'nav.search', 9],
  ['committee', 'nav.committee', 10, ['committee', 'secretary']],
  ['secretary', 'nav.secretary', 11, ['secretary']],
]

export default function App() {
  const { t } = useTranslation()
  return (
    <Routes>
      <Route path="/" element={<PublicOnlyRoute><Landing /></PublicOnlyRoute>} />
      <Route path="/login" element={<PublicOnlyRoute><Login /></PublicOnlyRoute>} />
      <Route path="/register" element={<PublicOnlyRoute><Register /></PublicOnlyRoute>} />

      <Route element={<ProtectedRoute><AppShell /></ProtectedRoute>}>
        {LATER_SCREENS.map(([path, label, step, roles]) => (
          <Route
            key={path}
            path={path}
            element={
              roles ? (
                <ProtectedRoute roles={roles}><ComingSoon title={t(label)} step={step} /></ProtectedRoute>
              ) : (
                <ComingSoon title={t(label)} step={step} />
              )
            }
          />
        ))}
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
