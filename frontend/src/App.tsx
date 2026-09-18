import { Navigate, Route, Routes } from 'react-router-dom'

import { AuthProvider } from '@/auth/AuthContext'
import RequireAuth from '@/auth/RequireAuth'
import MainLayout from '@/layouts/MainLayout'
import FabricsPage from '@/pages/FabricsPage'
import HomePage from '@/pages/HomePage'
import LoginPage from '@/pages/LoginPage'
import ProbadorPage from '@/pages/ProbadorPage'
import ProfilePage from '@/pages/ProfilePage'
import RegisterPage from '@/pages/RegisterPage'
import TallerPage from '@/pages/TallerPage'
import TrialPage from '@/pages/TrialPage'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<MainLayout />}>
          {/* Públicas: el catálogo de telas es el escaparate de la tienda y se
              navega sin cuenta. */}
          <Route index element={<HomePage />} />
          <Route path="telas" element={<FabricsPage />} />
          <Route path="entrar" element={<LoginPage />} />
          <Route path="registro" element={<RegisterPage />} />

          {/* Requieren sesión. El backend las protege igualmente; esto solo
              evita enseñar una pantalla que iba a fallar. */}
          <Route element={<RequireAuth />}>
            <Route path="taller" element={<TallerPage />} />
            <Route path="taller/:id" element={<TrialPage />} />
            <Route path="probador" element={<ProbadorPage />} />
            <Route path="perfil" element={<ProfilePage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </AuthProvider>
  )
}
